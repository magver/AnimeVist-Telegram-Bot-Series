"""
Standalone AnimeVist Series Auto Announcer.
Monitors AnimeVost & Shikimori APIs for newly released episodes
and publishes rich cards with posters and genre navigation to Telegram (#онгоинг).
"""

import os
import sys
import re
import json
import time
import math
import urllib.request
import urllib.parse
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
    HAS_PIL = True
except ImportError:
    Image = ImageDraw = ImageFont = ImageFilter = ImageEnhance = None
    HAS_PIL = False



if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram_sender import (
    TelegramSender,
    load_config,
    load_seen_from_supabase,
    save_seen_to_supabase
)
from news_announcer import prepare_hd_poster

SEEN_FILE = os.path.join(os.path.dirname(__file__), 'seen_episodes.json')

def load_seen_episodes():
    seen = set()
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, 'r', encoding='utf-8') as f:
                seen.update(json.load(f))
        except Exception:
            pass
    try:
        remote_seen = load_seen_from_supabase(category='episode')
        seen.update(remote_seen)
    except Exception:
        pass
    return seen

def save_seen_episodes(seen_set):
    try:
        with open(SEEN_FILE, 'w', encoding='utf-8') as f:
            items = list(seen_set)[-1000:]
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        save_seen_to_supabase(seen_set, category='episode')
    except Exception:
        pass

def clean_title(raw):
    cleaned = re.sub(r'\[.*?\]', '', raw).strip()
    parts = [p.strip() for p in cleaned.split('/')]
    ru = parts[0] if len(parts) > 0 else raw
    eng = parts[1] if len(parts) > 1 else ''
    return ru, eng

def extract_latest_episode_num(raw_title, series_data):
    """
    Extracts the true latest episode number.
    Prioritizes actual uploaded episode keys from series_data to avoid internal video CDN IDs,
    and uses title brackets as a reliable secondary source.
    """
    # 1. Check keys in series_data (AnimeVost keys e.g. '1 серия', '10 серия')
    series_keys_nums = []
    if isinstance(series_data, dict):
        for k in series_data.keys():
            m = re.search(r'(\d+)', str(k))
            if m:
                val = int(m.group(1))
                if 0 < val < 2000:
                    series_keys_nums.append(val)
    elif isinstance(series_data, str) and series_data.strip():
        # Match keys before colon in json-like string: '10 серия': '1460465236'
        key_matches = re.findall(r"['\"`](\d+)[^'\"`:]*?['\"`]\s*:", series_data)
        for k in key_matches:
            val = int(k)
            if 0 < val < 2000:
                series_keys_nums.append(val)

    if series_keys_nums:
        return max(series_keys_nums)

    # 2. Fallback: Parse bracket contents in raw_title
    bracket_matches = re.findall(r'\[(.*?)\]', raw_title)
    for b in bracket_matches:
        # Ignore future schedule brackets e.g. [11 серия - 12 сентября]
        if '-' in b and any(m in b.lower() for m in ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек', '202']):
            continue
        # Check patterns like [1-10 из 12], [10 из 12], [10 серия]
        m = re.search(r'(?:^|\D)(?:\d+\s*-\s*)?(\d+)\s*(?:из|серия|эп|\/|$)', b, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 0 < val < 2000:
                return val

    return 1

def extract_episode_details(raw_title, series_data):
    """
    Extracts both the current released episode number and the total episode count.
    Returns (cur_ep, total_ep), e.g. (16, 24) or (16, None)
    """
    cur_ep = extract_latest_episode_num(raw_title, series_data)
    total_ep = None

    bracket_matches = re.findall(r'\[(.*?)\]', str(raw_title))
    for b in bracket_matches:
        m = re.search(r'из\s*(\d+)\+?', b, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 0 < val < 2000:
                    total_ep = val
                    break
            except ValueError:
                pass

    if not total_ep:
        m2 = re.search(r'из\s*(\d+)\+?', str(raw_title), re.IGNORECASE)
        if m2:
            try:
                val = int(m2.group(1))
                if 0 < val < 2000:
                    total_ep = val
            except ValueError:
                pass

    return cur_ep, total_ep

def clean_search_title(raw_title):
    if not raw_title:
        return ""
    # Strip brackets like [1-12 из 12], [ТВ], [OVA]
    t = re.sub(r'\[.*?\]', '', raw_title)
    # Strip season and format indicators in parentheses
    t = re.sub(r'\s*\([^)]*(?:сезон|тв|фильм|ova|ona|спешл|recap|пересказ)[^)]*\)', '', t, flags=re.IGNORECASE)
    # Strip trailing season phrases
    t = re.sub(r'\s+2nd Season.*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+3rd Season.*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+4th Season.*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+Season\s+\d+.*', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s+\d+\s+сезон.*', '', t, flags=re.IGNORECASE)
    return t.strip()

def fetch_kitsu_poster(title_eng, title_ru=None):
    """
    Fetches ultra-high-resolution original poster from Kitsu API.
    Kitsu frequently stores full original prints up to 1600x2400.
    """
    for candidate in [title_eng, title_ru]:
        if not candidate:
            continue
        clean_q = clean_search_title(candidate)
        if not clean_q or len(clean_q) < 3:
            continue
        try:
            url = f"https://kitsu.io/api/edge/anime?filter[text]={urllib.parse.quote(clean_q)}&page[limit]=1"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)', 'Accept': 'application/vnd.api+json'}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=3.5) as r:
                d = json.loads(r.read())
            items = d.get('data', [])
            if items:
                post = items[0]['attributes'].get('posterImage', {})
                orig = post.get('original') or post.get('large')
                if orig and 'http' in orig:
                    return orig
        except Exception:
            pass
    return None

def resolve_best_poster(shiki_poster, vost_poster, title_ru=None, title_eng=None):
    """
    Ensures maximum visual quality for anime posters.
    Prioritizes Shikimori GraphQL HD (700x1000px+), Kitsu Original (up to 1600px+),
    and AnimeVost preview, completely eliminating 404s and placeholders.
    """
    if shiki_poster and isinstance(shiki_poster, str):
        low = shiki_poster.lower()
        if 'missing' not in low and '404' not in low and low.startswith('http'):
            return shiki_poster

    # Try Kitsu for high-res original
    kitsu = fetch_kitsu_poster(title_eng, title_ru)
    if kitsu and isinstance(kitsu, str) and kitsu.startswith('http'):
        return kitsu

    if vost_poster and isinstance(vost_poster, str):
        if not vost_poster.startswith('http'):
            return f"https://animevost.org{vost_poster}"
        return vost_poster

    return "https://raw.githubusercontent.com/magver/AnimeVist/main/assets/banner.png"

def get_system_font(size, bold=False):
    # 1. Project bundled TrueType fonts (works everywhere: Windows, Linux, Mac, Docker)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    bundled_bold = os.path.join(base_dir, 'assets', 'fonts', 'font_bold.ttf')
    bundled_reg = os.path.join(base_dir, 'assets', 'fonts', 'font_regular.ttf')

    bundled = bundled_bold if bold else bundled_reg
    if os.path.isfile(bundled):
        try:
            return ImageFont.truetype(bundled, size)
        except Exception:
            pass

    # 2. System fonts with Cyrillic support
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_vector_star(draw, cx, cy, r_outer=10, r_inner=4.8, color=(251, 191, 36, 255)):
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color)

def draw_vector_bolt(draw, cx, cy, h=16, color=(255, 255, 255, 255)):
    pts = [
        (cx + 2, cy - h//2),
        (cx - h//3, cy + 1),
        (cx, cy + 1),
        (cx - 2, cy + h//2),
        (cx + h//3, cy - 1),
        (cx, cy - 1)
    ]
    draw.polygon(pts, fill=color)

def render_episode_poster_overlay(img_path_or_url, title_ru, cur_ep, total_ep=None, rating=None, out_path=None):
    """
    Renders a cinematic glassmorphism card on the upper part of the poster
    featuring the anime title, episode ratio ("cur / total серия"), rating, and watermark.
    Returns path to the output image.
    """
    if not img_path_or_url or not HAS_PIL:
        return img_path_or_url


    try:
        local_path = img_path_or_url
        if str(img_path_or_url).startswith('http://') or str(img_path_or_url).startswith('https://'):
            local_path = prepare_hd_poster(img_path_or_url)

        if not local_path or not os.path.isfile(local_path):
            return img_path_or_url

        im = Image.open(local_path).convert("RGBA")
        w, h = im.size

        if w < 1000 or h < 1400:
            scale = max(1000 / w, 1400 / h)
            scale = min(scale, 3.0)
            new_w, new_h = int(w * scale), int(h * scale)
            im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            w, h = im.size

        # 1. Smooth gradient at TOP 45% for contrast
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        grad_h = int(h * 0.45)
        for y in range(grad_h):
            factor = 1.0 - (y / float(grad_h))
            alpha = int(225 * (factor ** 1.35))
            ov_draw.line([(0, y), (w, y)], fill=(6, 9, 18, alpha))
        im = Image.alpha_composite(im, overlay)

        # 2. Card layout & Logo preparation
        logo_path = os.path.join(os.path.dirname(__file__), 'assets', 'logo.png')
        has_logo = os.path.isfile(logo_path)
        logo_img = None
        if has_logo:
            try:
                logo_img = Image.open(logo_path).convert("RGBA")
            except Exception as e:
                print(f"[Poster] Warning loading logo: {e}")
                has_logo = False

        card_margin_x = int(w * 0.038)
        card_w = w - (card_margin_x * 2)
        card_r = int(w * 0.026)
        card_y = int(h * 0.065)

        if total_ep and str(total_ep) not in ('?', 'None', '0'):
            ep_text = f"{cur_ep} / {total_ep} серия"
        else:
            ep_text = f"{cur_ep} серия"

        # Adaptive typography
        title_font_size = max(24, int(w * 0.036))
        badge_font_size = max(19, int(w * 0.026))

        font_title = get_system_font(title_font_size, bold=True)
        font_badge = get_system_font(badge_font_size, bold=True)

        dummy = ImageDraw.Draw(im)

        pad_y = int(w * 0.032)
        pad_x = int(w * 0.04)
        badge_row_h = int(badge_font_size * 1.8)

        # Estimate card height for logo sizing
        est_card_h = pad_y * 2 + title_font_size * 2 + int(title_font_size * 0.3) + int(w * 0.02) + badge_row_h
        logo_size = int(est_card_h * 0.88) if has_logo else 0

        # Word wrap title to fit card (leaving space for logo if present)
        words = (title_ru or 'Новая серия').split()
        lines = []
        cur_line = []
        max_title_w = (card_w - logo_size - pad_x * 2 - int(w * 0.03)) if has_logo else (card_w - pad_x * 2)
        for word in words:
            test_line = " ".join(cur_line + [word])
            bbox = dummy.textbbox((0, 0), test_line, font=font_title)
            if bbox[2] - bbox[0] <= max_title_w:
                cur_line.append(word)
            else:
                if cur_line:
                    lines.append(" ".join(cur_line))
                cur_line = [word]
        if cur_line:
            lines.append(" ".join(cur_line))
        lines = lines[:2]
        if len(words) > 0 and len(lines) == 2 and words[-1] not in lines[1]:
            lines[1] = lines[1][:len(lines[1])-3] + '...'

        line_spacing = int(title_font_size * 0.28)
        title_total_h = len(lines) * title_font_size + (len(lines) - 1) * line_spacing

        card_h = pad_y * 2 + title_total_h + int(w * 0.020) + badge_row_h
        card_x = card_margin_x

        # Exact logo position inside card
        if has_logo:
            logo_size = int(card_h * 0.88)
            logo_rx = card_w - pad_x - logo_size
            logo_ry = (card_h - logo_size) // 2

        # 3. Frosted Glass Backdrop
        bg_crop = im.crop((card_x, card_y, card_x + card_w, card_y + card_h))
        blurred = bg_crop.resize((card_w, card_h), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(22))
        enh_b = ImageEnhance.Brightness(blurred).enhance(0.42)
        enh_c = ImageEnhance.Color(enh_b).enhance(1.4)

        plate = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        m_mask = Image.new("L", (card_w, card_h), 0)
        ImageDraw.Draw(m_mask).rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=card_r, fill=255)
        plate.paste(enh_c, (0, 0), m_mask)

        # Gradient tint overlay (Midnight Indigo with Cyberpunk accents)
        tint = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        t_draw = ImageDraw.Draw(tint)
        for y in range(card_h):
            ratio = y / float(card_h)
            r = int(10 + 6 * ratio)
            g = int(14 + 2 * ratio)
            b = int(28 + 8 * ratio)
            a = int(220 + 20 * ratio)
            t_draw.line([(0, y), (card_w, y)], fill=(r, g, b, a))

        glow = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        g_draw = ImageDraw.Draw(glow)
        g_draw.ellipse((-int(card_w * 0.05), -int(card_h * 0.3), int(card_w * 0.4), int(card_h * 0.8)), fill=(0, 229, 255, 30))
        if has_logo:
            g_draw.ellipse((logo_rx - 20, logo_ry - 20, logo_rx + logo_size + 20, logo_ry + logo_size + 20), fill=(236, 72, 153, 40))
            g_draw.ellipse((logo_rx - 10, logo_ry - 10, logo_rx + logo_size + 10, logo_ry + logo_size + 10), fill=(0, 229, 255, 35))
        glow = glow.filter(ImageFilter.GaussianBlur(int(card_h * 0.3)))
        tint = Image.alpha_composite(tint, glow)

        plate.paste(tint, (0, 0), m_mask)

        # 4. Premium Borders & Highlights
        p_draw = ImageDraw.Draw(plate)
        p_draw.rounded_rectangle(
            (0, 0, card_w - 1, card_h - 1),
            radius=card_r,
            fill=None,
            outline=(99, 102, 241, 190),
            width=2
        )
        p_draw.line([(card_r + 2, 1), (card_w - card_r - 2, 1)], fill=(255, 255, 255, 175), width=1)
        p_draw.line([(1, card_r + 2), (1, int(card_h * 0.7))], fill=(0, 229, 255, 140), width=1)

        # Draw Title
        curr_y = pad_y
        for line in lines:
            p_draw.text((pad_x, curr_y), line, fill=(255, 255, 255, 255), font=font_title)
            curr_y += title_font_size + line_spacing

        curr_y += int(w * 0.012)

        # Episode Pill with Vector Bolt
        cur_x = pad_x
        bolt_h = int(badge_font_size * 0.85)
        bolt_space = bolt_h + 8

        ep_bbox = p_draw.textbbox((0, 0), ep_text, font=font_badge)
        ep_tw = ep_bbox[2] - ep_bbox[0]
        ep_pill_w = ep_tw + bolt_space + int(badge_font_size * 0.9)
        ep_pill_h = badge_row_h
        ep_pill_r = ep_pill_h // 2

        p_draw.rounded_rectangle(
            (cur_x, curr_y, cur_x + ep_pill_w, curr_y + ep_pill_h),
            radius=ep_pill_r,
            fill=(37, 99, 235, 220),
            outline=(96, 165, 250, 240),
            width=1
        )
        pill_cy = curr_y + ep_pill_h / 2.0
        bolt_cx = cur_x + int(badge_font_size * 0.6) + bolt_h // 4
        draw_vector_bolt(p_draw, bolt_cx, pill_cy, h=bolt_h, color=(255, 255, 255, 255))
        p_draw.text((bolt_cx + bolt_h // 2 + 6, pill_cy), ep_text, fill=(255, 255, 255, 255), font=font_badge, anchor='lm')

        cur_x += ep_pill_w + int(w * 0.02)

        # Rating Pill with Vector Star
        if rating and str(rating) != '—':
            score_val = str(rating)
            s_bbox = p_draw.textbbox((0, 0), score_val, font=font_badge, anchor='lm')
            s_tw = s_bbox[2] - s_bbox[0]
            star_dia = int(badge_font_size * 0.8)
            rate_pill_w = s_tw + star_dia + int(badge_font_size * 1.3)
            rate_pill_h = badge_row_h
            rate_pill_r = rate_pill_h // 2

            p_draw.rounded_rectangle(
                (cur_x, curr_y, cur_x + rate_pill_w, curr_y + rate_pill_h),
                radius=rate_pill_r,
                fill=(217, 119, 6, 220),
                outline=(251, 191, 36, 240),
                width=1
            )
            rate_cy = curr_y + rate_pill_h / 2.0
            star_cx = cur_x + int(badge_font_size * 0.7) + star_dia // 2
            star_r = star_dia // 2
            draw_vector_star(p_draw, star_cx, rate_cy, r_outer=star_r, r_inner=star_r * 0.48, color=(255, 255, 255, 255))
            p_draw.text((star_cx + star_dia // 2 + 5, rate_cy), score_val, fill=(255, 255, 255, 255), font=font_badge, anchor='lm')

        # 5. Insert Neon Logo INSIDE plate
        if has_logo and logo_img:
            logo_resized = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            plate.paste(logo_resized, (logo_rx, logo_ry), logo_resized)

        # Shadow
        shadow = Image.new("RGBA", (card_w + 30, card_h + 30), (0, 0, 0, 0))
        sh_draw = ImageDraw.Draw(shadow)
        sh_draw.rounded_rectangle((15, 15, card_w + 15, card_h + 15), radius=card_r, fill=(0, 0, 0, 220))
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        im.paste(shadow, (card_x - 15, card_y - 15), shadow)
        im.paste(plate, (card_x, card_y), plate)


        if not out_path:
            import hashlib
            h_key = hashlib.md5(f"{title_ru}_{cur_ep}_{total_ep}_{rating}".encode('utf-8')).hexdigest()[:12]
            cache_dir = os.path.join(os.path.dirname(__file__), 'scratch', 'news_cache')
            os.makedirs(cache_dir, exist_ok=True)
            out_path = os.path.join(cache_dir, f"ep_overlay_{h_key}.jpg")

        im.convert("RGB").save(out_path, "JPEG", quality=95, optimize=True)
        return out_path
    except Exception as e:
        print(f"[Announcer] Poster overlay generation warning ({e}), falling back to base poster.")
        return img_path_or_url

def format_genre_hashtags(genre_str, ep_num=None, app_name='AnimeVist'):
    """
    Generates Russian genre navigation hashtags for rapid filtering in Telegram.
    """
    tags = []
    if genre_str:
        raw_items = re.split(r'[,/]', str(genre_str))
        for raw in raw_items:
            clean = re.sub(r'[^\w\s]', '', raw.strip()).lower().replace(' ', '_')
            if clean and len(clean) > 2 and clean not in tags:
                if clean in ('сенен', 'сенён'): clean = 'сёнэн'
                elif clean in ('седзе', 'сёдзе'): clean = 'сёдзё'
                elif clean == 'психологическое': clean = 'психология'
                tags.append(f"#{clean}")

    # Cap genres to top 4
    tags = tags[:4]

    if ep_num:
        tags.append(f"#серия{ep_num}")
    tags.append("#онгоинг")
    tags.append(f"#{app_name.lower()}")
    return " ".join(tags)

_shiki_cache = {}

def fetch_shikimori_info(title_ru, title_eng=None):
    """
    Queries Shikimori GraphQL (https://shikimori.io/api/graphql) for maximum quality
    retina / original posters (700x1000px+), verified ratings, and Russian genres.
    Falls back to Kitsu for ultra-high-resolution artwork.
    """
    cache_key = f"{title_ru}|{title_eng or ''}"
    if cache_key in _shiki_cache:
        return _shiki_cache[cache_key]

    clean_ru = clean_search_title(title_ru)
    clean_en = clean_search_title(title_eng) if title_eng else ""
    search_q = clean_ru or clean_en
    if not search_q:
        _shiki_cache[cache_key] = None
        return None

    safe_q = search_q.replace('"', '\\"').replace('\n', ' ')
    query = f"""
    {{
      animes(search: "{safe_q}", limit: 2) {{
        id
        name
        russian
        score
        genres {{
          name
          russian
        }}
        poster {{
          originalUrl
          main2xUrl
          mainUrl
        }}
      }}
    }}
    """
    headers = {'User-Agent': 'AnimeVistBot/2.0', 'Content-Type': 'application/json'}
    try:
        req = urllib.request.Request(
            'https://shikimori.io/api/graphql',
            data=json.dumps({'query': query}).encode('utf-8'),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=3.5) as r:
            d = json.loads(r.read())
        animes = d.get('data', {}).get('animes', [])
        if animes:
            top = animes[0]
            p = top.get('poster', {})
            poster_url = p.get('originalUrl') or p.get('main2xUrl') or p.get('mainUrl')
            if poster_url and ('missing' in poster_url.lower() or '404' in poster_url.lower()):
                poster_url = None

            genres_list = [g.get('russian') or g.get('name') for g in top.get('genres', [])]
            info = {
                'title_ru': top.get('russian') or title_ru,
                'title_eng': top.get('name') or title_eng,
                'poster': poster_url,
                'rating': str(top.get('score', '—')),
                'genres': ", ".join(genres_list[:5])
            }
            _shiki_cache[cache_key] = info
            return info
    except Exception:
        pass

    # Secondary attempt with English title if Russian didn't match
    if clean_en and clean_en != clean_ru:
        safe_en = clean_en.replace('"', '\\"').replace('\n', ' ')
        query_en = f"""
        {{
          animes(search: "{safe_en}", limit: 2) {{
            id
            name
            russian
            score
            genres {{
              name
              russian
            }}
            poster {{
              originalUrl
              main2xUrl
              mainUrl
            }}
          }}
        }}
        """
        try:
            req2 = urllib.request.Request(
                'https://shikimori.io/api/graphql',
                data=json.dumps({'query': query_en}).encode('utf-8'),
                headers=headers
            )
            with urllib.request.urlopen(req2, timeout=3.5) as r2:
                d2 = json.loads(r2.read())
            animes2 = d2.get('data', {}).get('animes', [])
            if animes2:
                top2 = animes2[0]
                p2 = top2.get('poster', {})
                poster_url2 = p2.get('originalUrl') or p2.get('main2xUrl') or p2.get('mainUrl')
                if poster_url2 and ('missing' in poster_url2.lower() or '404' in poster_url2.lower()):
                    poster_url2 = None

                genres_list2 = [g.get('russian') or g.get('name') for g in top2.get('genres', [])]
                info2 = {
                    'title_ru': top2.get('russian') or title_ru,
                    'title_eng': top2.get('name') or title_eng,
                    'poster': poster_url2,
                    'rating': str(top2.get('score', '—')),
                    'genres': ", ".join(genres_list2[:5])
                }
                _shiki_cache[cache_key] = info2
                return info2
        except Exception:
            pass

    _shiki_cache[cache_key] = None
    return None

def get_seen_max_episodes(seen_set):
    """
    Builds a dictionary {vost_id: max_seen_episode_number}
    to guarantee that older or already posted episodes of an ongoing anime
    are never posted again in automatic mode.
    """
    seen_max = {}
    for item in seen_set:
        parts = str(item).split('_')
        if len(parts) == 2:
            try:
                v_id = str(parts[0])
                ep_n = int(parts[1])
                if v_id not in seen_max or ep_n > seen_max[v_id]:
                    seen_max[v_id] = ep_n
            except ValueError:
                pass
    return seen_max

def is_episode_already_seen(vost_id, ep_num, seen_set, seen_max_map=None):
    v_str = str(vost_id)
    ep_key = f"{v_str}_{ep_num}"
    if ep_key in seen_set or str(ep_key) in seen_set:
        return True
    if seen_max_map is not None:
        try:
            curr_ep = int(ep_num)
            max_ep = seen_max_map.get(v_str)
            if max_ep is not None and curr_ep <= max_ep:
                return True
        except (ValueError, TypeError):
            pass
    return False

def fetch_latest_episodes(quantity=40):
    url = f"https://api.animevost.org/v1/last?page=1&quantity={quantity}"
    req = urllib.request.Request(url, headers={'User-Agent': 'AnimeVistBot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            return res.get('data', [])
    except Exception as e:
        print(f"[Announcer] Error fetching AnimeVost: {e}")
        return []

def is_in_quiet_hours(start_hour: int = 23, end_hour: int = 8) -> bool:
    """Check if current time is within quiet hours (MSK / UTC+3)."""
    msk_hour = time.gmtime(time.time() + 3 * 3600).tm_hour
    if start_hour > end_hour:
        # Crosses midnight, e.g. 23:00 to 08:00
        return msk_hour >= start_hour or msk_hour < end_hour
    elif start_hour < end_hour:
        # e.g. 01:00 to 07:00
        return start_hour <= msk_hour < end_hour
    return False

def run_series_check(dry_run=False):
    config = load_config()
    ann_conf = config.get('announcer', {})
    if not ann_conf.get('enable_series_releases', True) and not dry_run:
        print("[Announcer] Публикация серий отключена в настройках (enable_series_releases = False).")
        return 0

    quiet_enabled = ann_conf.get('releases_quiet_hours_enabled', True)
    quiet_start = int(ann_conf.get('releases_quiet_hours_start', 23))
    quiet_end = int(ann_conf.get('releases_quiet_hours_end', 8))
    quiet_action = ann_conf.get('releases_quiet_action', 'skip')
    silent_always = ann_conf.get('releases_silent_notifications', False)

    is_quiet_now = quiet_enabled and is_in_quiet_hours(quiet_start, quiet_end)
    if is_quiet_now and quiet_action == 'skip' and not dry_run:
        print(f"[Announcer] 🌙 Ночной тихий режим ({quiet_start}:00-{quiet_end}:00 МСК). Публикация онгоингов отложена до утра.")
        return 0

    silent_post = bool(silent_always or (is_quiet_now and quiet_action == 'silent'))

    sender = TelegramSender()
    seen = load_seen_episodes()
    seen_max = get_seen_max_episodes(seen)

    items = fetch_latest_episodes(quantity=40)
    if not items:
        print("[Announcer] No items fetched.")
        return 0

    max_per_cycle = ann_conf.get('max_releases_per_cycle', 3)
    published_count = 0

    # Seed on first run if empty
    if len(seen) == 0:
        print("[Announcer] Initializing seen_episodes database with current releases (first run)...")
        for it in items:
            ep_num = extract_latest_episode_num(it.get('title', ''), it.get('series'))
            seen.add(f"{it.get('id')}_{ep_num}")
        save_seen_episodes(seen)
        print("[Announcer] Initialization complete. Future new episodes will be posted automatically.")
        return 0

    for it in items:
        if published_count >= max_per_cycle:
            break

        vost_id = it.get('id')
        raw_title = it.get('title', '')
        title_ru, title_eng = clean_title(raw_title)
        latest_ep_num, total_ep_num = extract_episode_details(raw_title, it.get('series'))

        if is_episode_already_seen(vost_id, latest_ep_num, seen, seen_max):
            continue

        ep_key = f"{vost_id}_{latest_ep_num}"
        print(f"[Announcer] Новая серия обнаружена: {title_ru} ({latest_ep_num} серия)")

        shiki_info = fetch_shikimori_info(title_ru, title_eng)
        rating_str = shiki_info.get('rating', '—') if shiki_info else '—'
        genres_str = (shiki_info.get('genres') if shiki_info else None) or it.get('genre') or 'Аниме, Приключения'
        
        raw_poster = resolve_best_poster(
            shiki_info.get('poster') if shiki_info else None,
            it.get('urlImagePreview'),
            title_ru=title_ru,
            title_eng=title_eng
        )
        poster_url = prepare_hd_poster(raw_poster)
        poster_with_overlay = render_episode_poster_overlay(
            poster_url,
            title_ru=title_ru,
            cur_ep=latest_ep_num,
            total_ep=total_ep_num,
            rating=rating_str
        )

        app_name = config.get('app', {}).get('name', 'AnimeVist')
        hashtags = format_genre_hashtags(genres_str, latest_ep_num, app_name)

        eng_sub = f"🎬 <i>{title_eng}</i>\n\n" if title_eng else "\n"
        caption = (
            f"🔥 <b>Вышла {latest_ep_num} серия «{title_ru}»!</b>\n"
            f"{eng_sub}"
            f"⭐️ <b>Рейтинг:</b> {rating_str} / 10\n"
            f"🎭 <b>Жанры:</b> {genres_str}\n\n"
            f"🎙 <b>Доступно в {app_name}:</b>\n"
            f"• ⚡ <b>AnimeVost</b> (Прямой поток 1080p/720p без задержек)\n"
            f"• 💬 <b>Субтитры & Озвучка</b> (по мере выхода релиз-групп)\n\n"
            f"✨ <i>Смотрите без рекламы, со сквозной синхронизацией ПК ↔ Android и автопропуском опенингов!</i>\n\n"
            f"{hashtags}"
        )

        # Build watch URL that directs to the specific episode in AnimeVist
        watch_url = f"https://magver.github.io/AnimeVist-Telegram-Bot/open.html?animeId=vost-{vost_id}&episode={latest_ep_num}"
        keyboard = [
            [
                {"text": "🎬 Смотреть в приложении", "url": watch_url}
            ]
        ]

        show_chat = config.get('announcer', {}).get('show_chat_button', False)
        chat_url = config.get('app', {}).get('chat_invite_url', '').strip()
        if show_chat and chat_url and chat_url.startswith('http'):
            keyboard.append([
                {"text": "💬 Обсудить серию в чате", "url": chat_url}
            ])

        reply_markup = {"inline_keyboard": keyboard}

        if dry_run:
            print("[DRY-RUN] Preview:")
            print(caption)
            print("Poster:", poster_with_overlay)
            print("Hashtags:", hashtags)
            print("Reply markup:", reply_markup)
        else:
            res = sender.send_photo(poster_with_overlay, caption=caption, reply_markup=reply_markup, disable_notification=silent_post)
            if res.get('ok'):
                print(f"[Announcer] ✅ Опубликовано: {ep_key}")
            else:
                print(f"[Announcer] ❌ Ошибка публикации: {res.get('description')}")
            seen.add(ep_key)
            seen_max[str(vost_id)] = max(seen_max.get(str(vost_id), 0), int(latest_ep_num))
            save_seen_episodes(seen)

        published_count += 1
        time.sleep(1)

    return published_count

def get_recent_releases_for_preview(count=15, only_unseen=True):
    """
    Fetches recent releases from AnimeVost with generated preview captions,
    posters, and metadata for the web dashboard studio.
    Filters out already published episodes by default.
    """
    config = load_config()
    seen = load_seen_episodes()
    seen_max = get_seen_max_episodes(seen)
    items = fetch_latest_episodes(quantity=40)
    if not items:
        return []

    results = []
    app_name = config.get('app', {}).get('name', 'AnimeVist')

    for it in items:
        vost_id = it.get('id')
        raw_title = it.get('title', '')
        title_ru, title_eng = clean_title(raw_title)
        latest_ep_num, total_ep_num = extract_episode_details(raw_title, it.get('series'))
        ep_key = f"{vost_id}_{latest_ep_num}"
        is_seen = is_episode_already_seen(vost_id, latest_ep_num, seen, seen_max)

        if only_unseen and is_seen:
            continue

        shiki_info = fetch_shikimori_info(title_ru, title_eng)
        rating_str = shiki_info.get('rating', '—') if shiki_info else '—'
        genres_str = (shiki_info.get('genres') if shiki_info else None) or it.get('genre') or 'Аниме, Приключения'
        
        raw_poster = resolve_best_poster(
            shiki_info.get('poster') if shiki_info else None,
            it.get('urlImagePreview'),
            title_ru=title_ru,
            title_eng=title_eng
        )
        poster_url = raw_poster
        hashtags = format_genre_hashtags(genres_str, latest_ep_num, app_name)
        eng_sub = f"🎬 <i>{title_eng}</i>\n\n" if title_eng else "\n"
        caption = (
            f"🔥 <b>Вышла {latest_ep_num} серия «{title_ru}»!</b>\n"
            f"{eng_sub}"
            f"⭐️ <b>Рейтинг:</b> {rating_str} / 10\n"
            f"🎭 <b>Жанры:</b> {genres_str}\n\n"
            f"🎙 <b>Доступно в {app_name}:</b>\n"
            f"• ⚡ <b>AnimeVost</b> (Прямой поток 1080p/720p без задержек)\n"
            f"• 💬 <b>Субтитры & Озвучка</b> (по мере выхода релиз-групп)\n\n"
            f"✨ <i>Смотрите без рекламы, со сквозной синхронизацией ПК ↔ Android и автопропуском опенингов!</i>\n\n"
            f"{hashtags}"
        )

        ep_ratio_str = f"{latest_ep_num} / {total_ep_num}" if total_ep_num else str(latest_ep_num)
        ep_display_str = f"{latest_ep_num} / {total_ep_num} серия" if total_ep_num else f"{latest_ep_num} серия"

        watch_url = f"https://magver.github.io/AnimeVist-Telegram-Bot/open.html?animeId=vost-{vost_id}&episode={latest_ep_num}"

        results.append({
            "id": vost_id,
            "vost_id": vost_id,
            "ep_num": latest_ep_num,
            "cur_ep": latest_ep_num,
            "total_ep": total_ep_num,
            "ep_ratio": ep_ratio_str,
            "ep_display": ep_display_str,
            "ep_key": ep_key,
            "title": title_ru,
            "title_ru": title_ru,
            "title_eng": title_eng,
            "rating": rating_str,
            "genres": genres_str,
            "poster_url": poster_url,
            "caption": caption,
            "default_caption": caption,
            "hashtags": hashtags,
            "watch_url": watch_url,
            "button_text": "🎬 Смотреть в приложении",
            "button_url": watch_url,
            "already_seen": is_seen
        })

        if len(results) >= count:
            break

    return results

def publish_single_custom_episode(vost_id, ep_num, caption, poster_url=None, reply_markup=None, title_ru=None, total_ep=None, rating=None, disable_notification=False):
    sender = TelegramSender()
    if poster_url and (poster_url.startswith('http') or os.path.isfile(poster_url)):
        target_poster = poster_url
        if poster_url.startswith('http'):
            try:
                local_file = prepare_hd_poster(poster_url)
                if local_file and os.path.isfile(local_file):
                    target_poster = local_file
            except Exception:
                pass

        try:
            overlay_file = render_episode_poster_overlay(
                target_poster,
                title_ru=title_ru or "Аниме",
                cur_ep=ep_num,
                total_ep=total_ep,
                rating=rating
            )
            if overlay_file and os.path.isfile(overlay_file):
                target_poster = overlay_file
        except Exception as e:
            print(f"[Announcer] Poster overlay generation warning ({e}), using raw poster.")

        res = sender.send_photo(target_poster, caption=caption, reply_markup=reply_markup, disable_notification=disable_notification)
    else:
        res = sender.send_message(caption, reply_markup=reply_markup, disable_notification=disable_notification)

    if res.get('ok'):
        seen = load_seen_episodes()
        ep_key = f"{vost_id}_{ep_num}"
        seen.add(ep_key)
        save_seen_episodes(seen)
    return res

if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    run_series_check(dry_run=dry)
