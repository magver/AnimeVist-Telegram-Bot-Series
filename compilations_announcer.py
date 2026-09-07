"""
AnimeVist Dynamic & Curated Anime Compilations Engine.
Generates themed Top 3-10 anime collections (Must-Watch, Hidden Gems, Mindfuck, Sci-Fi, etc.),
combines all posters into a single high-resolution collage banner using Pillow,
prevents repeats by tracking seen anime IDs, and posts rich cards with hashtags (#подборка).
"""

import os
import sys
import io
import json
import time
import random
import urllib.request
import re
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

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

SEEN_ANIMES_FILE = os.path.join(os.path.dirname(__file__), 'seen_compilation_animes.json')
LAST_COMPILATION_FILE = os.path.join(os.path.dirname(__file__), 'last_compilation_time.json')
COLLAGE_DIR = os.path.join(os.path.dirname(__file__), 'scratch')

# Curated Thematic Catalog with 523 hand-picked masterpieces (50-61 per theme)
THEMES = {   'cyberpunk_scifi': {   'candidates': [   {   'en': 'Cyberpunk: Edgerunners',
                                                 'genres': 'Экшен, Киберпанк',
                                                 'hook': 'Парень из трущоб становится наемником-соло в безжалостном '
                                                         'Найт-Сити.',
                                                 'id': 42310,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx120377-ayZPoxiWt4Li.jpg',
                                                 'ru': 'Киберпанк: Бегущие по краю',
                                                 'score': '8.50'},
                                             {   'en': 'Ghost in the Shell',
                                                 'genres': 'Киберпанк, Sci-Fi',
                                                 'hook': 'Майор Мотоко Кусанаги расследует киберпреступления на грани '
                                                         'человечности.',
                                                 'id': 29325,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx43-Y6EjeEMM14dj.png',
                                                 'ru': 'Призрак в доспехах',
                                                 'score': '8.30'},
                                             {   'en': 'AKIRA',
                                                 'genres': 'Фантастика, Экшен',
                                                 'hook': 'Байкер в разрушенном Нео-Токио пробуждает колоссальную '
                                                         'разрушительную мощь.',
                                                 'id': 47,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx47-4CR68arv452h.jpg',
                                                 'ru': 'Акира',
                                                 'score': '7.90'},
                                             {   'en': 'Vivy: Fluorite Eye’s Song',
                                                 'genres': 'Музыка, Фантастика',
                                                 'hook': 'Андроид-певица должна предотвратить восстание машин длиною в '
                                                         '100 лет.',
                                                 'id': 46095,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx128546-UIwyhuhjxmL0.jpg',
                                                 'ru': 'Виви: Песнь флюоритового глаза',
                                                 'score': '8.20'},
                                             {   'en': 'TRIGUN',
                                                 'genres': 'Экшен, Sci-Fi',
                                                 'hook': 'Пацифист Вэш Ураган скитается по пустынной планете, спасая '
                                                         'людей.',
                                                 'id': 6,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6-wd4saT1JzStH.jpg',
                                                 'ru': 'Триган (1998)',
                                                 'score': '8.00'},
                                             {   'en': 'Ginga Eiyuu Densetsu',
                                                 'genres': 'Космос, Военное',
                                                 'hook': 'Грандиозное противостояние двух гениальных стратегов в '
                                                         'масштабах космоса.',
                                                 'id': 820,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx820-x5dNLNFeKb8B.png',
                                                 'ru': 'Легенда о героях Галактики',
                                                 'score': '8.80'},
                                             {   'en': 'Last Exile',
                                                 'genres': 'Стимпанк, Приключения',
                                                 'hook': 'Юные пилоты ваншипа оказываются втянуты в воздушную войну '
                                                         'двух империй.',
                                                 'id': 97,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx97-Loi1Ppy4quXy.jpg',
                                                 'ru': 'Изгнанник',
                                                 'score': '7.40'},
                                             {   'en': 'Eve no Jikan Movie',
                                                 'genres': 'Повседневность, Sci-Fi',
                                                 'hook': 'В уютном кафе стирается социальная грань между людьми и '
                                                         'андроидами.',
                                                 'id': 7465,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7465-gBh82FNppI9h.png',
                                                 'ru': 'Время Евы',
                                                 'score': '7.70'},
                                             {   'en': 'Akudama Drive',
                                                 'genres': 'Экшен, Киберпанк',
                                                 'hook': 'Отряд отпетых преступников Кансая берется за '
                                                         'самоубийственное ограбление.',
                                                 'id': 41433,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx116566-PPIVQt359vQY.jpg',
                                                 'ru': 'Акудама Драйв',
                                                 'score': '7.50'},
                                             {   'en': 'PSYCHO-PASS',
                                                 'genres': 'Киберпанк, Триллер',
                                                 'hook': 'Система «Сивилла» вычисляет вероятность преступления еще до '
                                                         'его совершения.',
                                                 'id': 13601,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx13601-i42VFuHpqEOJ.jpg',
                                                 'ru': 'Психопаспорт',
                                                 'score': '8.40'},
                                             {   'en': 'Tengen Toppa Gurren Lagann',
                                                 'genres': 'Экшен, Меха',
                                                 'hook': 'Симон и Камина бурят путь наверх сквозь пространство, бросая '
                                                         'вызов Вселенной.',
                                                 'id': 2001,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2001-XwRnjzGeFWRQ.png',
                                                 'ru': 'Гуррен-Лаганн',
                                                 'score': '8.50'},
                                             {   'en': 'Cowboy Bebop',
                                                 'genres': 'Фантастика, Экшен',
                                                 'hook': 'Охотники за головами бороздят Солнечную систему под звуки '
                                                         'бессмертного джаза.',
                                                 'id': 1,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1-GCsPm7waJ4kS.png',
                                                 'ru': 'Ковбой Бибоп',
                                                 'score': '8.60'},
                                             {   'en': 'Planetes',
                                                 'genres': 'Drama, Romance, Sci-Fi',
                                                 'hook': 'Умная и реалистичная твёрдая научная фантастика о буднях '
                                                         'космических сборщиков.',
                                                 'id': 329,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx329-4xwXdazRA7Ph.png',
                                                 'ru': 'Странники',
                                                 'score': '8.25'},
                                             {   'en': 'Den-noh Coil',
                                                 'genres': 'Adventure, Comedy, Drama',
                                                 'hook': 'Таинственные кибер-призраки и заговоры в мире повсеместных '
                                                         'умных очков.',
                                                 'id': 2164,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2164-4tUI4MJCZQO3.png',
                                                 'ru': 'Кибер-виток',
                                                 'score': '8.02'},
                                             {   'en': 'Space Dandy',
                                                 'genres': 'Comedy, Sci-Fi',
                                                 'hook': 'Фонтан визуального стиля и безумных галактических '
                                                         'приключений стиляги Дэнди.',
                                                 'id': 20057,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20057-tG83EpH5Gu8K.jpg',
                                                 'ru': 'Космический Денди',
                                                 'score': '7.89'},
                                             {   'en': 'Texhnolyze',
                                                 'genres': 'Action, Drama, Psychological',
                                                 'hook': 'Бескомпромиссно мрачный киберпанк о закате человечества в '
                                                         'подземном мегаполисе.',
                                                 'id': 26,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx26-ADSztyHBNO39.jpg',
                                                 'ru': 'Технолайз',
                                                 'score': '7.76'},
                                             {   'en': 'Macross Plus',
                                                 'genres': 'Action, Drama, Mecha',
                                                 'hook': 'Противостояние пилотов новейших истребителей и опасного '
                                                         'виртуального айдола.',
                                                 'id': 474,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx474-lyjbbltW5ZX4.png',
                                                 'ru': 'Макросс Плюс',
                                                 'score': '7.73'},
                                             {   'en': 'Knights of Sidonia',
                                                 'genres': 'Action, Fantasy, Mecha',
                                                 'hook': 'Отчаянная битва гигантского корабля-колонии человечества '
                                                         'против инопланетных гауна.',
                                                 'id': 19775,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx19775-h4Fc1q5qsGfP.png',
                                                 'ru': 'Рыцари Сидонии',
                                                 'score': '7.63'},
                                             {   'en': 'BLAME! Ver.0.11',
                                                 'genres': 'Action, Mecha, Sci-Fi',
                                                 'hook': 'Киберпанковский постапокалипсис в бесконечном многоуровневом '
                                                         'Городе-Мегаструктуре.',
                                                 'id': 1055,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx1055-k99fJWHZoKy3.png',
                                                 'ru': 'Блейм!',
                                                 'score': '5.92'},
                                             {   'en': 'Ghost in the Shell: Stand Alone Complex',
                                                 'genres': 'Action, Mystery, Psychological',
                                                 'hook': 'Культовый детективный сериал 9-го отдела о кибертерроризме и '
                                                         'взломе призраков.',
                                                 'id': 467,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx467-mBTtIoR13qs2.jpg',
                                                 'ru': 'Призрак в доспехах: Синдром одиночки',
                                                 'score': '8.42'},
                                             {   'en': 'Mobile Suit GUNDAM Iron Blooded Orphans',
                                                 'genres': 'Action, Drama, Mecha',
                                                 'hook': 'Жестокая и честная космическая драма о юных наёмниках с '
                                                         'Марса.',
                                                 'id': 31251,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx21268-6dKrz26PPUvk.jpg',
                                                 'ru': 'Мобильный воин Гандам: Железнокровные сироты',
                                                 'score': '8.07'},
                                             {   'en': 'Serial Experiments Lain',
                                                 'genres': 'Drama, Mystery, Psychological',
                                                 'hook': 'Культовое киберпанковское исследование слияния сознания с '
                                                         'Сетью.',
                                                 'id': 339,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx339-xF2wp1NQuQ4r.png',
                                                 'ru': 'Эксперименты Лэйн',
                                                 'score': '8.1'},
                                             {   'en': 'Outlaw Star Pilot',
                                                 'genres': 'Action, Sci-Fi',
                                                 'hook': 'Золотая эпоха космических приключений, сокровищ и дуэлей на '
                                                         'кораблях.',
                                                 'id': 4650,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/4650.jpg',
                                                 'ru': 'Звёздные рыцари со звезды изгоев: Пилотный эпизод',
                                                 'score': '6.89'},
                                             {   'en': 'Redline',
                                                 'genres': 'Action, Romance, Sci-Fi',
                                                 'hook': 'Абсолютный триумф рисованной от руки анимации о безумнейших '
                                                         'межгалактических гонках.',
                                                 'id': 6675,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6675-NF4tFzAxSjkj.png',
                                                 'ru': 'Красная черта',
                                                 'score': '8.29'},
                                             {   'en': 'Dr. STONE',
                                                 'genres': 'Action, Adventure, Comedy',
                                                 'hook': 'Возрождение цивилизации и технологий с нуля благодаря силе '
                                                         'науки.',
                                                 'id': 38691,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105333-GybuoSoOZfpH.jpg',
                                                 'ru': 'Доктор Стоун',
                                                 'score': '8.26'},
                                             {   'en': 'ASTRA LOST IN SPACE',
                                                 'genres': 'Adventure, Mystery, Sci-Fi',
                                                 'hook': 'Захватывающее космическое выживание школьников с '
                                                         'неожиданными тайнами.',
                                                 'id': 39198,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx107663-gfIpy1h36kUL.jpg',
                                                 'ru': 'Астра, затерянная в космосе',
                                                 'score': '8.07'},
                                             {   'en': '86 EIGHTY-SIX',
                                                 'genres': 'Action, Drama, Mecha',
                                                 'hook': 'Трагическая война беспилотников, внутри которых тайно '
                                                         'погибают отвергнутые люди.',
                                                 'id': 41457,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx116589-KawXHB6sApFt.jpg',
                                                 'ru': 'Восемьдесят шесть',
                                                 'score': '8.35'},
                                             {   'en': 'World Trigger',
                                                 'genres': 'Action, Sci-Fi',
                                                 'hook': 'Тактический командный Sci-Fi с глубоко продуманной боевой '
                                                         'системой.',
                                                 'id': 24405,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20729-DnBXnUxFon1B.png',
                                                 'ru': 'Импульс мира',
                                                 'score': '7.58'},
                                             {   'en': 'ALDNOAH.ZERO',
                                                 'genres': 'Action, Mecha, Sci-Fi',
                                                 'hook': 'Война землян против технологически превосходящей марсианской '
                                                         'империи.',
                                                 'id': 22729,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx20632-Mkgbtvi1kmhD.jpg',
                                                 'ru': 'Альдноа.Зеро',
                                                 'score': '7.38'},
                                             {   'en': 'No Guns Life',
                                                 'genres': 'Action, Drama, Sci-Fi',
                                                 'hook': 'Киберпанк-детектив с револьвером вместо головы, защищающий '
                                                         'права аугментированных.',
                                                 'id': 39539,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx108478-yHMnmQCtHSDb.jpg',
                                                 'ru': 'Жизнь без оружия',
                                                 'score': '6.86'},
                                             {   'en': 'Dimension W',
                                                 'genres': 'Action, Sci-Fi',
                                                 'hook': 'Охота за нелегальными катушками бесконечной энергии из '
                                                         'таинственного 4-го измерения.',
                                                 'id': 31163,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21256-ErFGk90Kr5Ab.jpg',
                                                 'ru': 'Измерение «W»',
                                                 'score': '7.17'},
                                             {   'en': 'PSYCHO-PASS 2',
                                                 'genres': 'Киберпанк, Детектив',
                                                 'hook': 'Аканэ Цунэмори сталкивается с преступником, которого '
                                                         'всевидящая система Сивилла не замечает.',
                                                 'id': 23281,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20513-pVQqYhMwBGoh.jpg',
                                                 'ru': 'Психопаспорт 2',
                                                 'score': '7.10'},
                                             {   'en': 'Star Blazers: Space Battleship Yamato 2199',
                                                 'genres': 'Sci-Fi, Космос',
                                                 'hook': 'Последняя надежда вымирающей Земли отправляется в '
                                                         'путешествие за спасительным очистителем.',
                                                 'id': 12029,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx12029-qIY5Bkh4sFKx.png',
                                                 'ru': 'Космический линкор Ямато 2199',
                                                 'score': '8.00'},
                                             {   'en': 'Mobile Suit Gundam: The Witch from Mercury',
                                                 'genres': 'Меха, Sci-Fi',
                                                 'hook': 'Девушка с окраины солнечной системы поступает в академию '
                                                         'пилотов мобильных доспехов.',
                                                 'id': 49828,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx139274-0NJTOKWHdDew.png',
                                                 'ru': 'Гандам: Ведьма с Меркурия',
                                                 'score': '7.80'},
                                             {   'en': 'Mobile Suit Gundam: Iron-Blooded Orphans-Urdr Hunt',
                                                 'genres': 'Меха, Драма',
                                                 'hook': 'Марсианские дети-наёмники восстают против жестокого гнёта '
                                                         'Земной федерации.',
                                                 'id': 62805,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx114842-AMEG5qd5h6Fw.jpg',
                                                 'ru': 'Гандам: Железнокровные сироты',
                                                 'score': '5.40'},
                                             {   'en': 'Bubblegum Crisis',
                                                 'genres': 'Киберпанк, Экшен',
                                                 'hook': 'Четыре наёмницы в высокотехнологичных бронекостюмах '
                                                         'истребляют вышедших из-под контроля бумеров.',
                                                 'id': 1347,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx1347-4NzCZYQQwIjb.jpg',
                                                 'ru': 'Кризис каждый день',
                                                 'score': '7.00'},
                                             {   'en': 'Knights of Sidonia: Love Woven in the Stars',
                                                 'genres': 'Sci-Fi, Меха',
                                                 'hook': 'Решающая битва людей-пилотов мобильных стражей против '
                                                         'колоссальных космических Гауна.',
                                                 'id': 35759,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99730-pG6lazHo6pKG.jpg',
                                                 'ru': 'Рыцари Сидонии: Финал',
                                                 'score': '7.30'},
                                             {   'en': 'Mobile Suit Gundam 00',
                                                 'genres': 'Меха, Экшен',
                                                 'hook': 'Организация Celestial Being искореняет мировые войны с '
                                                         'помощью превосходящих роботов Гандам.',
                                                 'id': 2581,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2581-MLEf00dNAfqY.jpg',
                                                 'ru': 'Гандам 00',
                                                 'score': '7.80'},
                                             {   'en': 'Metropolis',
                                                 'genres': 'Sci-Fi, Киберпанк',
                                                 'hook': 'Шедевр Ринтаро и Осаму Тэдзуки о расслоении гигантского '
                                                         'города и прекрасном роботе Тиме.',
                                                 'id': 522,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx522-4Sp8QlrufkG5.jpg',
                                                 'ru': 'Метрополис',
                                                 'score': '7.40'},
                                             {   'en': 'Memories',
                                                 'genres': 'Sci-Fi, Антология',
                                                 'hook': 'Три визуально безупречные научно-фантастические новеллы от '
                                                         'Кацухиро Отомо.',
                                                 'id': 1462,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1462-wHe4bW5b6XRE.png',
                                                 'ru': 'Воспоминания о будущем',
                                                 'score': '7.50'},
                                             {   'en': 'Appleseed',
                                                 'genres': 'Киберпанк, Меха',
                                                 'hook': 'Элитный спецназовец Дюнан и ее напарник-киборг Бриарей '
                                                         'защищают утопический Олимп.',
                                                 'id': 937,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx937-2SYiMKI3qPkp.jpg',
                                                 'ru': 'Яблочное зёрнышко',
                                                 'score': '5.90'},
                                             {   'en': 'Guilty Crown',
                                                 'genres': 'Sci-Fi, Экшен',
                                                 'hook': 'Школьник обретает «Силу Королей», позволяющую извлекать '
                                                         'оружие из сердец людей.',
                                                 'id': 10793,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10793-KCysCbrVNqK9.jpg',
                                                 'ru': 'Корона грешника',
                                                 'score': '6.90'},
                                             {   'en': 'Outlaw Star',
                                                 'genres': 'Космос, Приключения',
                                                 'hook': 'Джин Старвинд и его команда на уникальном космическом '
                                                         'корабле ищут Галактическую жилу.',
                                                 'id': 400,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx400-CJ2duQT3dCX1.png',
                                                 'ru': 'Звёздный рыцарь Аутло',
                                                 'score': '7.50'},
                                             {   'en': 'God Eater',
                                                 'genres': 'Экшен, Sci-Fi',
                                                 'hook': 'Элитные бойцы с живым оружием «Дзинги» сражаются против '
                                                         'неуязвимых чудовищ Арагами.',
                                                 'id': 27631,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20849-TvJpY8iLEcYG.jpg',
                                                 'ru': 'Пожиратель богов',
                                                 'score': '6.90'},
                                             {   'en': 'Ghost in the Shell: Arise Specials',
                                                 'genres': 'Киберпанк, Экшен',
                                                 'hook': 'Молодая майор Кусанаги собирает будущую легендарную команду '
                                                         '9-го отдела.',
                                                 'id': 21575,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/20776.jpg',
                                                 'ru': 'Призрак в доспехах: У истоков',
                                                 'score': '5.60'},
                                             {   'en': 'Roujin Z',
                                                 'genres': 'Sci-Fi, Сатира',
                                                 'hook': 'Вышедшая из-под контроля медицинская кровать с ИИ берет '
                                                         'старика в заложники и штурмует город.',
                                                 'id': 2000,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2000-BFVMqByhjMNW.jpg',
                                                 'ru': 'Старик Зет',
                                                 'score': '6.80'},
                                             {   'en': 'Macross Frontier',
                                                 'genres': 'Меха, Космос',
                                                 'hook': 'Колониальный флот сталкивается с биомеханическими '
                                                         'инсектоидами Ваджра под песни Ранки Ли.',
                                                 'id': 3572,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx3572-qYJhokKdsnZR.png',
                                                 'ru': 'Макросс Фронтир',
                                                 'score': '7.60'},
                                             {   'en': 'Toward the Terra',
                                                 'genres': 'Sci-Fi, Космос',
                                                 'hook': 'Гонимые обществом мутанты Мю ведут многолетнюю борьбу за '
                                                         'возвращение на колыбель-Землю.',
                                                 'id': 2560,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2560-fGJFfEvVBGMB.png',
                                                 'ru': 'К Тесле',
                                                 'score': '6.10'},
                                             {   'en': 'Mobile Suit Gundam Wing',
                                                 'genres': 'Меха, Военный',
                                                 'hook': 'Пятеро юных пилотов на Гандамах отправляются на Землю ради '
                                                         'освобождения космических колоний.',
                                                 'id': 90,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b90-umBjF3yaeIdo.png',
                                                 'ru': 'Гандам Крыло',
                                                 'score': '7.10'},
                                             {   'en': 'Patlabor: The Movie',
                                                 'genres': 'Sci-Fi, Меха',
                                                 'hook': 'Элитный отряд робо-патруля расследует смертельный '
                                                         'компьютерный вирус в строительных лейборах.',
                                                 'id': 1095,
                                                 'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1095-uHF4BmIHLzbG.png',
                                                 'ru': 'Полиция будущего: Фильм',
                                                 'score': '7.60'}],
                           'desc': 'Мрачное будущее, аугментации, искусственный интеллект и неоновые мегаполисы:',
                           'key': 'cyberpunk_scifi',
                           'name': '🌆 Киберпанк, космос и фантастика',
                           'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx120377-ayZPoxiWt4Li.jpg',
                           'shiki_genre': None,
                           'shiki_order': None,
                           'tags': '#киберпанк #фантастика #scifi',
                           'title': 'Культовый киберпанк и фантастика 🌆'},
    'dark_horror': {   'candidates': [   {   'en': 'Berserk',
                                             'genres': 'Хоррор, Тёмное фэнтези',
                                             'hook': 'Брутальная сага о выживании мечника Гатса в безжалостном '
                                                     'средневековом мире.',
                                             'id': 33,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx33-PSwfE5B0gejI.jpg',
                                             'ru': 'Берсерк',
                                             'score': '8.40'},
                                         {   'en': 'Tokyo Ghoul',
                                             'genres': 'Хоррор, Драма',
                                             'hook': 'Студент Канэки становится полугулем и пытается сохранить '
                                                     'человечность в мире хищников.',
                                             'id': 22319,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b20605-k665mVkSug8D.jpg',
                                             'ru': 'Токийский гуль',
                                             'score': '7.60'},
                                         {   'en': 'Parasyte -the maxim-',
                                             'genres': 'Хоррор, Sci-Fi',
                                             'hook': 'Инопланетный паразит захватывает правую руку школьника, втягивая '
                                                     'в смертельную войну.',
                                             'id': 22535,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20623-dUARfggnNDOe.jpg',
                                             'ru': 'Паразит: Учение о жизни',
                                             'score': '8.10'},
                                         {   'en': 'Hellsing Ultimate',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Непобедимый вампир Алукард защищает Британскую империю от орд '
                                                     'нечисти и фашистов.',
                                             'id': 777,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx777-F6547pSAR2Zd.jpg',
                                             'ru': 'Хеллсинг OVA',
                                             'score': '8.10'},
                                         {   'en': 'Claymore',
                                             'genres': 'Тёмное фэнтези, Хоррор',
                                             'hook': 'Воительницы с серебряными глазами охотятся на пожирающих людей '
                                                     'демонов Йома.',
                                             'id': 1818,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1818-KieLJv0qo3mO.jpg',
                                             'ru': 'Клеймор',
                                             'score': '7.40'},
                                         {   'en': 'Another',
                                             'genres': 'Хоррор, Детектив',
                                             'hook': 'В проклятом школьном классе оживает смертоносное проклятие, '
                                                     'уносящее жизни одну за другой.',
                                             'id': 11111,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11111-gvvE5bBYsyFo.png',
                                             'ru': 'Иная',
                                             'score': '7.10'},
                                         {   'en': 'Elfen Lied',
                                             'genres': 'Хоррор, Драма',
                                             'hook': 'Мутант-диклониус Люси с невидимыми смертоносными векторами '
                                                     'сбегает из лаборатории.',
                                             'id': 226,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx226-MibyRKhIrnTe.png',
                                             'ru': 'Эльфийская песнь',
                                             'score': '6.80'},
                                         {   'en': 'The Promised Neverland',
                                             'genres': 'Триллер, Хоррор',
                                             'hook': 'Сироты идеального приюта узнают, что их растят на корм '
                                                     'чудовищам, и готовят побег.',
                                             'id': 37779,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101759-8UR7r9MNVpz2.jpg',
                                             'ru': 'Обещанный Неверленд',
                                             'score': '8.30'},
                                         {   'en': 'Shiki',
                                             'genres': 'Хоррор, Мистика',
                                             'hook': 'Затерянная в горах деревня медленно вымирает из-за нашествия '
                                                     'восставших вампиров.',
                                             'id': 7724,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7724-NwNnRsI34eDa.jpg',
                                             'ru': 'Усопшие',
                                             'score': '7.50'},
                                         {   'en': 'Deadman Wonderland',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Ложно обвинённый подросток попадает в смертельную '
                                                     'тюрьму-аттракцион с боями на крови.',
                                             'id': 71724,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Страна чудес смертников',
                                             'score': '7.20'},
                                         {   'en': 'Gantz',
                                             'genres': 'Хоррор, Sci-Fi',
                                             'hook': 'Погибшие люди возвращаются к жизни чёрной сферой, чтобы '
                                                     'охотиться на жестоких пришельцев.',
                                             'id': 79352,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Ганц',
                                             'score': '7.10'},
                                         {   'en': 'When They Cry',
                                             'genres': 'Хоррор, Психология',
                                             'hook': 'Праздник Ватанагаси в тихой деревне оборачивается кровавыми '
                                                     'циклами безумия.',
                                             'id': 934,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx934-wjMlVEl4CWwg.jpg',
                                             'ru': 'Когда плачут цикады',
                                             'score': '7.60'},
                                         {   'en': 'Corpse Party',
                                             'genres': 'Хоррор, Кровь',
                                             'hook': 'Школьники переносят ритуал дружбы в проклятую начальную школу, '
                                                     'кишащую призраками.',
                                             'id': 15037,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx15037-32PupkILJcuv.jpg',
                                             'ru': 'Вечеринка мертвецов',
                                             'score': '5.90'},
                                         {   'en': 'AJIN: Demi-Human',
                                             'genres': 'Хоррор, Триллер',
                                             'hook': 'Бессмертные существа Адзины становятся объектом жестокой охоты '
                                                     'спецслужб.',
                                             'id': 31580,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21341-Pyc7SkMEuGsl.jpg',
                                             'ru': 'Получеловек',
                                             'score': '7.10'},
                                         {   'en': 'GOBLIN SLAYER',
                                             'genres': 'Тёмное фэнтези, Экшен',
                                             'hook': 'Прагматичный мечник посвятил всю жизнь безжалостному истреблению '
                                                     'коварных гоблинов.',
                                             'id': 37349,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101165-v5NwPXWPFDuD.jpg',
                                             'ru': 'Убийца гоблинов',
                                             'score': '7.10'},
                                         {   'en': 'Dark Gathering',
                                             'genres': 'Хоррор, Мистика',
                                             'hook': 'Девочка собирает коллекцию опаснейших духов Японии, чтобы '
                                                     'отомстить за душу матери.',
                                             'id': 52505,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx152802-ENRcnqD5axhQ.jpg',
                                             'ru': 'Тёмное собрание',
                                             'score': '7.50'},
                                         {   'en': 'Mieruko-chan',
                                             'genres': 'Хоррор, Комедия',
                                             'hook': 'Школьница видит жутких потусторонних монстров и изо всех сил '
                                                     'делает вид, что не замечает их.',
                                             'id': 48483,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx131083-sKGHkpVDksaZ.png',
                                             'ru': 'Девочка, которая видит это',
                                             'score': '7.20'},
                                         {   'en': 'Devilman Crybaby',
                                             'genres': 'Хоррор, Трагедия',
                                             'hook': 'Кровавая деконструкция природы человека и демонов на пороге '
                                                     'судного дня.',
                                             'id': 35120,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98460-bLtH2c3jd6sV.png',
                                             'ru': 'Человек-дьявол: Плакса',
                                             'score': '7.60'},
                                         {   'en': 'Dorohedoro',
                                             'genres': 'Тёмное фэнтези, Комедия',
                                             'hook': 'Человек с головой рептилии Кайман охотится на магов в поисках '
                                                     'своей настоящей личности.',
                                             'id': 38668,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105228-I4xr84QS9Pvk.jpg',
                                             'ru': 'Дорохедоро',
                                             'score': '7.90'},
                                         {   'en': 'Hell’s Paradise',
                                             'genres': 'Тёмное фэнтези, Экшен',
                                             'hook': 'Приговорённые к смерти преступники и их палачи ищут бессмертие '
                                                     'на адском острове.',
                                             'id': 46569,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx128893-Gc2t8b8M0mVu.jpg',
                                             'ru': 'Адский рай',
                                             'score': '8.00'},
                                         {   'en': 'INUYASHIKI LAST HERO',
                                             'genres': 'Sci-Fi, Триллер',
                                             'hook': 'Старик и старшеклассник превращаются в боевых киборгов, выбрав '
                                                     'противоположные пути добра и зла.',
                                             'id': 34542,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97922-qrGn5fkQinDs.jpg',
                                             'ru': 'Инуясики',
                                             'score': '7.40'},
                                         {   'en': 'Blood+',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Сая Отонаси с помощью собственной крови уничтожает крылатых '
                                                     'монстров-рукокрылых.',
                                             'id': 150,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx150-YRcwKiJEXcLx.png',
                                             'ru': 'Кровь+',
                                             'score': '7.30'},
                                         {   'en': 'Dusk Maiden of Amnesia',
                                             'genres': 'Хоррор, Романтика',
                                             'hook': 'Парень общается с прекрасным призраком Юко, расследуя тайну её '
                                                     'гибели в старой школе.',
                                             'id': 12445,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx12445-hKIXQW3vA4iz.jpg',
                                             'ru': 'Амнезия сумеречной девы',
                                             'score': '7.50'},
                                         {   'en': 'Ghost Hunt',
                                             'genres': 'Хоррор, Мистика',
                                             'hook': 'Группа экстрасенсов и ученых исследует реальные дома с '
                                                     'привидениями и полтергейстом.',
                                             'id': 1571,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1571-rgWSFoPDZhzS.png',
                                             'ru': 'Охота на привидений',
                                             'score': '7.30'},
                                         {   'en': 'Hell Girl',
                                             'genres': 'Хоррор, Мистика',
                                             'hook': 'Энма Ай утягивает обидчиков в ад по полуночному запросу на '
                                                     'таинственном сайте.',
                                             'id': 228,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx228-J2J1CI4jfyeC.jpg',
                                             'ru': 'Адская девочка',
                                             'score': '7.20'},
                                         {   'en': 'Kabaneri of the Iron Fortress',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Бронированный паровоз прорывается сквозь орды стальных '
                                                     'зомби-кабанэ в паропанковой Японии.',
                                             'id': 28623,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21196-2PfPfIDrxKki.jpg',
                                             'ru': 'Кабанери железной крепости',
                                             'score': '7.00'},
                                         {   'en': 'Terra Formars',
                                             'genres': 'Sci-Fi, Хоррор',
                                             'hook': 'Генетически модифицированные космонавты сражаются с чудовищными '
                                                     'тараканами-мутантами на Марсе.',
                                             'id': 22687,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx20629-xO8wxKYeXncc.png',
                                             'ru': 'Терраформирование',
                                             'score': '6.50'},
                                         {   'en': 'Castlevania',
                                             'genres': 'Тёмное фэнтези, Хоррор',
                                             'hook': 'Тревор Бельмонт, Алукард и Сифа ведут войну против обезумевшего '
                                                     'от горя Дракулы.',
                                             'id': 98316,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Кастлвания',
                                             'score': '8.20'},
                                         {   'en': 'Vampire Hunter D: Bloodlust',
                                             'genres': 'Хоррор, Постапокалипсис',
                                             'hook': 'Дампир Ди охотится за вампиром Майерлингом, похитившим дочь '
                                                     'богатого дворянина.',
                                             'id': 543,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx543-MAeWIDl4TwuG.png',
                                             'ru': 'Ди: Жажда крови',
                                             'score': '7.90'},
                                         {   'en': 'Attack on Titan Final Season',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Кульминация войны за остров Парадиз и начало Гул Земли.',
                                             'id': 40028,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx110277-sKUNXAsWMNFw.jpg',
                                             'ru': 'Атака титанов: Финал',
                                             'score': '8.70'},
                                         {   'en': 'Kurozuka',
                                             'genres': 'Хоррор, Самураи',
                                             'hook': 'Бессмертный мечник Куро преследует свою возлюбленную-вампиршу '
                                                     'сквозь века.',
                                             'id': 5039,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5039-F9HXvMsrQGP8.png',
                                             'ru': 'Куродзука',
                                             'score': '6.40'},
                                         {   'en': 'RIN ~Daughters of Mnemosyne~',
                                             'genres': 'Хоррор, Sci-Fi',
                                             'hook': 'Бессмертный частный детектив Рин распутывает изощренные дела в '
                                                     'Токио.',
                                             'id': 3342,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx3342-py3qPHF7NK3c.jpg',
                                             'ru': 'Дочери Мнемозины',
                                             'score': '6.70'},
                                         {   'en': 'Shigurui: Death Frenzy',
                                             'genres': 'Самураи, Хоррор',
                                             'hook': 'Бескомпромиссная кровавая дуэль двух искалеченных мастеров меча '
                                                     'перед лицом даймё.',
                                             'id': 2216,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx2216-90YquKJllawX.jpg',
                                             'ru': 'Одержимые смертью',
                                             'score': '6.90'},
                                         {   'en': 'Vampire Knight',
                                             'genres': 'Мистика, Драма',
                                             'hook': 'Дневной класс обычных школьников и Ночной класс аристократичных '
                                                     'вампиров под стражей Юки.',
                                             'id': 3457,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx3457-owSEHJYvflx5.jpg',
                                             'ru': 'Рыцарь-вампир',
                                             'score': '6.30'},
                                         {   'en': 'Tokyo Ghoul:re',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Следователь Сасаки Хайсэ возглавляет спецотряд людей с кагуне.',
                                             'id': 36511,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx100240-vJNaKd5HwPJ2.jpg',
                                             'ru': 'Токийский гуль: Перерождение',
                                             'score': '6.20'},
                                         {   'en': 'Hide-and-seek',
                                             'genres': 'Хоррор, Мистика',
                                             'hook': 'Дети в масках играют в заброшенном городе в прятки с настоящими '
                                                     'демонами.',
                                             'id': 50914,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113266-oXOhlbnWPh4n.jpg',
                                             'ru': 'Игра в прятки',
                                             'score': '4.90'},
                                         {   'en': 'Petshop of Horrors',
                                             'genres': 'Хоррор, Мистика',
                                             'hook': 'Граф Ди продает экзотических питомцев при строжайшем соблюдении '
                                                     'условий контракта.',
                                             'id': 326,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx326-dCwCoSAE7dWZ.jpg',
                                             'ru': 'Магазинчик ужасов',
                                             'score': '6.80'},
                                         {   'en': 'Ghost Stories',
                                             'genres': 'Хоррор, Комедия',
                                             'hook': 'Школьники случайно запечатывают и изгоняют городских духов из '
                                                     'заброшенной школы.',
                                             'id': 1281,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1281-1D6fuMnHwor0.png',
                                             'ru': 'Истории о привидениях',
                                             'score': '7.40'},
                                         {   'en': 'Ayakashi: Samurai Horror Tales',
                                             'genres': 'Хоррор, Фольклор',
                                             'hook': 'Три классические японские страшные легенды о духах и возмездии.',
                                             'id': 586,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx586-alDXEdRVYNU1.png',
                                             'ru': 'Аякаси: Самурайские ужасы',
                                             'score': '6.90'},
                                         {   'en': 'Blood-C',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Милая жрица Сая защищает город от древних тварей, пока не узнаёт '
                                                     'ужасающую правду.',
                                             'id': 10490,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10490-Rqx4jlTOMFWx.jpg',
                                             'ru': 'Кровь-C',
                                             'score': '6.20'},
                                         {   'en': 'High School of the Dead',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Группа выживших школьников пробивается сквозь толпы зомби в '
                                                     'охваченном пандемией городе.',
                                             'id': 8074,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx8074-YB63Ik96fjPj.png',
                                             'ru': 'Школа мертвецов',
                                             'score': '6.70'},
                                         {   'en': 'Genocyber',
                                             'genres': 'Хоррор, Киберпанк',
                                             'hook': 'Ужасающий кибернетический монстр Генокибер стирает в пыль целые '
                                                     'города и армии.',
                                             'id': 2775,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/2775-GrmImvJgETGn.png',
                                             'ru': 'Генокибер',
                                             'score': '5.30'},
                                         {   'en': 'Wicked City',
                                             'genres': 'Хоррор, Мистика',
                                             'hook': 'Тайная полиция людей и Черного Мира охраняет мирный договор '
                                                     'между расами от радикальных демонов.',
                                             'id': 1107,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx1107-YRi1VB2Y80g3.png',
                                             'ru': 'Город чудищ',
                                             'score': '6.10'},
                                         {   'en': 'GANTZ:O',
                                             'genres': 'Хоррор, CGI-экшен',
                                             'hook': 'Команда Ганца отправляется в ночную Осаку для истребления сотни '
                                                     'смертоносных мифологических монстров Нурарихёна.',
                                             'id': 32071,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx21496-b6R9F3FtIgWJ.jpg',
                                             'ru': 'Ганц: О',
                                             'score': '7.10'},
                                         {   'en': 'Hellsing',
                                             'genres': 'Хоррор, Вампиры',
                                             'hook': 'Алукард и Серас Виктория истребляют вампиров-фриков под джазовый '
                                                     'саундтрек.',
                                             'id': 270,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b270-S2ProngvO6BU.jpg',
                                             'ru': 'Хеллсинг (2001)',
                                             'score': '7.20'},
                                         {   'en': 'Resident Evil: Damnation',
                                             'genres': 'Хоррор, Боевик',
                                             'hook': 'Леон Кеннеди проникает в Восточную Славянскую Республику, где '
                                                     'повстанцы используют Лизунов.',
                                             'id': 9544,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx9544-rD8dGcCuSW2s.jpg',
                                             'ru': 'Обитель зла: Проклятие',
                                             'score': '6.70'},
                                         {   'en': 'AJIN: Demi-Human 2',
                                             'genres': 'Хоррор, Триллер',
                                             'hook': 'Кэи Нагаи и министерство объединяются против безжалостного '
                                                     'террориста-адзина Сато.',
                                             'id': 33253,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21799-0WB0vWJJ7mFX.jpg',
                                             'ru': 'Получеловек (2 сезон)',
                                             'score': '7.30'},
                                         {   'en': 'Kemonozume',
                                             'genres': 'Хоррор, Экшен',
                                             'hook': 'Кровавая драма о древнем клане пожирателей плоти Сёкудзинки и '
                                                     'охотниках Кимонофу.',
                                             'id': 1454,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1454-fyg2zIQz5Qsj.png',
                                             'ru': 'Когти зверя',
                                             'score': '7.10'},
                                         {   'en': 'Pupa',
                                             'genres': 'Хоррор, Мутации',
                                             'hook': 'Брат скармливает свою регенерирующую плоть заразившейся вирусом '
                                                     'Пупа сестре-монстру.',
                                             'id': 19315,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx19315-dWHH0pRxVCjq.jpg',
                                             'ru': 'Куколка',
                                             'score': '2.70'},
                                         {   'en': 'The Island of Giant Insects',
                                             'genres': 'Хоррор, Выживание',
                                             'hook': 'Выжившие в авиакатастрофе школьницы сталкиваются с кровожадными '
                                                     'гигантскими насекомыми на острове.',
                                             'id': 33421,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx106750-R3njaL8buS1F.jpg',
                                             'ru': 'Остров гигантских насекомых',
                                             'score': '5.70'}],
                       'desc': 'Леденящие кровь триллеры, жестокая борьба за жизнь и бескомпромиссная тьма:',
                       'key': 'dark_horror',
                       'name': '🩸 Мрачный хоррор, выживание и тёмное фэнтези',
                       'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b20605-k665mVkSug8D.jpg',
                       'shiki_genre': None,
                       'shiki_order': None,
                       'tags': '#хоррор #триллер #тёмное_фэнтези',
                       'title': 'Мрачный хоррор, выживание и тёмное фэнтези 🩸'},
    'epic_fantasy': {   'candidates': [   {   'en': 'VINLAND SAGA',
                                              'genres': 'Экшен, Приключения',
                                              'hook': 'Юный Торфинн жаждет мести за отца посреди завоевательных '
                                                      'походов викингов.',
                                              'id': 37521,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101348-2fhDFPCuMNiz.jpg',
                                              'ru': 'Сага о Винланде',
                                              'score': '8.70'},
                                          {   'en': 'Kenpuu Denki Berserk',
                                              'genres': 'Тёмное фэнтези, Военное',
                                              'hook': 'Одинокий мечник Гатс встречает Гриффита и вступает в Отряд '
                                                      'Сокола.',
                                              'id': 33,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx33-PSwfE5B0gejI.jpg',
                                              'ru': 'Берсерк (1997)',
                                              'score': '8.40'},
                                          {   'en': 'Made in Abyss',
                                              'genres': 'Приключения, Драма',
                                              'hook': 'Девочка Рико и робот Рэг спускаются в смертоносные глубины '
                                                      'великой Бездны.',
                                              'id': 34599,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97986-TQ7dCgbS3y5s.jpg',
                                              'ru': 'Созданный в Бездне',
                                              'score': '8.40'},
                                          {   'en': 'Kimetsu no Yaiba',
                                              'genres': 'Экшен, Сверхъестественное',
                                              'hook': 'Тандзиро становится истребителем демонов, чтобы исцелить '
                                                      'обращенную сестру.',
                                              'id': 38000,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101922-WBsBl0ClmgYL.jpg',
                                              'ru': 'Клинок, рассекающий демонов',
                                              'score': '8.30'},
                                          {   'en': 'Noragami',
                                              'genres': 'Мистика, Комедия',
                                              'hook': 'Бродячий бог Ято выполняет любые просьбы за монетку в 5 иен '
                                                      'ради своего храма.',
                                              'id': 20507,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20447-EoQXeygHaVCK.jpg',
                                              'ru': 'Бездомный бог',
                                              'score': '7.80'},
                                          {   'en': 'Kill la Kill',
                                              'genres': 'Экшен, Комедия',
                                              'hook': 'Рюко Матой с половиной ножниц ищет убийцу отца в элитной '
                                                      'академии.',
                                              'id': 18679,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b18679-lbkq7iYESoFW.png',
                                              'ru': 'Убей или умри',
                                              'score': '7.90'},
                                          {   'en': 'JoJo no Kimyou na Bouken (TV)',
                                              'genres': 'Экшен, Приключения',
                                              'hook': 'Эпическая сага поколений семьи Джостаров в схватке с древним '
                                                      'злом.',
                                              'id': 14719,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx14719-VT5dRzTBSZ0w.jpg',
                                              'ru': 'Невероятные приключения ДжоДжо',
                                              'score': '7.70'},
                                          {   'en': 'Dungeon Meshi',
                                              'genres': 'Фэнтези, Гурман',
                                              'hook': 'Отряд авантюристов спасает соратницу из брюха дракона, готовя '
                                                      'монстров на обед.',
                                              'id': 52701,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx153518-IVXPDY5ph3kO.jpg',
                                              'ru': 'Подземелье вкусностей',
                                              'score': '8.50'},
                                          {   'en': 'HUNTER×HUNTER (2011)',
                                              'genres': 'Экшен, Приключения',
                                              'hook': 'Гон и друзья преодолевают смертельные испытания невероятного '
                                                      'мира Охотников.',
                                              'id': 11061,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11061-y5gsT1hoHuHw.png',
                                              'ru': 'Охотник х Охотник',
                                              'score': '8.90'},
                                          {   'en': 'Sousou no Frieren',
                                              'genres': 'Фэнтези, Драма',
                                              'hook': 'Эльфийская волшебница познает тепло человеческих уз после '
                                                      'победы над Владыкой.',
                                              'id': 52991,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                              'ru': 'Провожающая в последний путь Фрирен',
                                              'score': '9.10'},
                                          {   'en': 'CLAYMORE',
                                              'genres': 'Тёмное фэнтези, Экшен',
                                              'hook': 'Воительницы с серебряными глазами очищают континент от '
                                                      'чудовищ-йома.',
                                              'id': 1818,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1818-KieLJv0qo3mO.jpg',
                                              'ru': 'Клеймор',
                                              'score': '7.40'},
                                          {   'en': 'Mushoku Tensei: Isekai Ittara Honki Dasu',
                                              'genres': 'Магия, Приключения',
                                              'hook': 'Переродившийся маг познает законы нового фантастического мира.',
                                              'id': 39535,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx108465-1ANspF1EWyFx.jpg',
                                              'ru': 'Реинкарнация безработного',
                                              'score': '8.20'},
                                          {   'en': 'Fate/Zero',
                                              'genres': 'Action, Drama, Fantasy',
                                              'hook': 'Грандиозная битва магов и мифических героев за право обладания '
                                                      'Граалем.',
                                              'id': 10087,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10087-M4Hd9qrHGrXk.png',
                                              'ru': 'Судьба/Начало',
                                              'score': '8.26'},
                                          {   'en': 'Fate/stay night: Unlimited Blade Works',
                                              'genres': 'Action, Fantasy, Supernatural',
                                              'hook': 'Невероятный визуальный пир и философская дуэль идеалов героя '
                                                      'справедливости.',
                                              'id': 22297,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx19603-ycT0pyEgDVQu.jpg',
                                              'ru': 'Судьба/Ночь схватки: Бесконечный мир клинков',
                                              'score': '8.18'},
                                          {   'en': 'Fullmetal Alchemist: Brotherhood',
                                              'genres': 'Action, Adventure, Drama',
                                              'hook': 'Эталон жанра о путешествии братьев Элриков и тайнах алхимии.',
                                              'id': 5114,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5114-nSWCgQlmOMtj.jpg',
                                              'ru': 'Стальной алхимик: Братство',
                                              'score': '9.11'},
                                          {   'en': 'Magi: The Labyrinth of Magic',
                                              'genres': 'Action, Adventure, Fantasy',
                                              'hook': 'Волшебное восточное приключение Аладдина и Али-Бабы по '
                                                      'сокровищницам джиннов.',
                                              'id': 14513,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx14513-HuUdrFFYftA7.jpg',
                                              'ru': 'Маги: Лабиринт магии',
                                              'score': '8.0'},
                                          {   'en': 'Yona of the Dawn',
                                              'genres': 'Action, Adventure, Comedy',
                                              'hook': 'Изгнанная принцесса собирает легендарных воинов-драконов ради '
                                                      'спасения царства.',
                                              'id': 25013,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20770-brCDvhTXlums.png',
                                              'ru': 'Йона на заре',
                                              'score': '8.04'},
                                          {   'en': 'GOBLIN SLAYER',
                                              'genres': 'Action, Adventure, Fantasy',
                                              'hook': 'Суровое и прагматичное тёмное фэнтези о зачистке самых коварных '
                                                      'тварей.',
                                              'id': 37349,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101165-v5NwPXWPFDuD.jpg',
                                              'ru': 'Убийца гоблинов',
                                              'score': '7.42'},
                                          {   'en': 'MUSHI-SHI',
                                              'genres': 'Adventure, Fantasy, Mystery',
                                              'hook': 'Гинко путешествует по Японии, исцеляя связь людей с первородной '
                                                      'магией муси.',
                                              'id': 457,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx457-l6cTtNgI9Bi6.png',
                                              'ru': 'Мастер муси',
                                              'score': '8.65'},
                                          {   'en': 'Ranking of Kings',
                                              'genres': 'Action, Adventure, Drama',
                                              'hook': 'Трогательная до слёз сказка о глухонемом принце Бодзи с чистым '
                                                      'храбрым сердцем.',
                                              'id': 40834,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113717-9sNnN8WRgK15.jpg',
                                              'ru': 'Рейтинг короля',
                                              'score': '8.48'},
                                          {   'en': 'The Seven Deadly Sins',
                                              'genres': 'Action, Adventure, Comedy',
                                              'hook': 'Могущественные рыцари королевства встают на защиту принцессы от '
                                                      'переворота.',
                                              'id': 23755,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20789-Ma5ouSYPkru9.jpg',
                                              'ru': 'Семь смертных грехов',
                                              'score': '7.59'},
                                          {   'en': 'Black Clover',
                                              'genres': 'Action, Adventure, Comedy',
                                              'hook': 'Парень без капли магии доказывает, что упорство способно '
                                                      'сокрушить любого мага.',
                                              'id': 34572,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97940-fyh8o7gNbha0.png',
                                              'ru': 'Чёрный клевер',
                                              'score': '8.14'},
                                          {   'en': 'Overlord',
                                              'genres': 'Action, Adventure, Fantasy',
                                              'hook': 'Могущественный маг-нежить захватывает новый мир ради славы '
                                                      'своей гробницы.',
                                              'id': 29803,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20832-vUNm5zrYWifc.jpg',
                                              'ru': 'Повелитель',
                                              'score': '7.89'},
                                          {   'en': 'D.Gray-man',
                                              'genres': 'Action, Adventure, Drama',
                                              'hook': 'Экзорцисты с Чистой Силой ведут вечную войну против '
                                                      'Тысячелетнего Графа.',
                                              'id': 1482,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1482-6jc8ZVSmHuLo.jpg',
                                              'ru': 'Ди Грэй-мен',
                                              'score': '8.0'},
                                          {   'en': 'Tower of God',
                                              'genres': 'Action, Adventure, Drama',
                                              'hook': 'Смертоносный подъем на вершину гигантской Башни, где '
                                                      'исполняются любые желания.',
                                              'id': 40221,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx115230-QHOdSN7yt8ab.jpg',
                                              'ru': 'Башня Бога',
                                              'score': '7.55'},
                                          {   'en': 'Fairy Tail',
                                              'genres': 'Action, Adventure, Comedy',
                                              'hook': 'Самая безбашенная гильдия магов защищает друзей силой '
                                                      'несокрушимой дружбы.',
                                              'id': 6702,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b6702-KI4qgSMyI8Pm.png',
                                              'ru': 'Хвост Феи',
                                              'score': '7.57'},
                                          {   'en': 'Grimgar of Fantasy and Ash',
                                              'genres': 'Action, Adventure, Drama',
                                              'hook': 'Реалистичное и атмосферное выживание новичков в опасном '
                                                      'незнакомом мире.',
                                              'id': 31859,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21428-dFVIHeZ8McBe.jpg',
                                              'ru': 'Гримгал пепла и иллюзий',
                                              'score': '7.66'},
                                          {   'en': 'The Heroic Legend of Arslan: Age of Heroes',
                                              'genres': 'Action, Adventure, Drama',
                                              'hook': 'Молодой принц собирает армию, чтобы вернуть захваченное врагами '
                                                      'королевство.',
                                              'id': 1762,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1762-acu1YWRQB4QA.jpg',
                                              'ru': 'Сказание об Арслане OVA',
                                              'score': '6.9'},
                                          {   'en': 'Is It Wrong to Try to Pick Up Girls in a Dungeon?',
                                              'genres': 'Action, Adventure, Comedy',
                                              'hook': 'Белл Кранел с богиней Гестией покоряет опаснейшие глубины '
                                                      'Подземелья Орарио.',
                                              'id': 28121,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20920-MTREwZOG4BAD.jpg',
                                              'ru': 'Может, я встречу тебя в подземелье?',
                                              'score': '7.52'},
                                          {   'en': 'Katanagatari',
                                              'genres': 'Action, Adventure, Romance',
                                              'hook': 'Поэтичное странствие за двенадцатью проклятыми клинками '
                                                      'легендарного кузнеца.',
                                              'id': 6594,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6594-xrrFyCacxUle.png',
                                              'ru': 'Истории мечей',
                                              'score': '8.29'},
                                          {   'en': 'Moribito: Guardian of the Spirit',
                                              'genres': 'Action, Adventure, Fantasy',
                                              'hook': 'Непобедимая копьеносица Бальса защищает проклятого юного принца '
                                                      'от наёмников.',
                                              'id': 1827,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1827-snIp62SY7ZFK.jpg',
                                              'ru': 'Хранитель священного духа',
                                              'score': '8.12'},
                                          {   'en': 'Tales of Zestiria the X',
                                              'genres': 'Action, Adventure, Fantasy',
                                              'hook': 'Пастырь Сорей путешествует по охваченному скверной миру ради '
                                                      'спасения душ.',
                                              'id': 30911,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21221-exaYgjct2K2c.jpg',
                                              'ru': 'Сказания Зестирии',
                                              'score': '7.21'},
                                          {   'en': 'Fate/stay night [Heaven’s Feel] III. spring song',
                                              'genres': 'Тёмное фэнтези, Драма',
                                              'hook': 'Мрачнейшая ветка Войны за Грааль, где любовь требует '
                                                      'пожертвовать целым миром.',
                                              'id': 33050,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21719-MSdTlkno0Z0u.jpg',
                                              'ru': 'Судьба: Прикосновение небес',
                                              'score': '8.50'},
                                          {   'en': 'the Garden of sinners Chapter 8: The Final Chapter',
                                              'genres': 'Мистика, Экшен',
                                              'hook': 'Девушка с мистическими глазами восприятия смерти расследует '
                                                      'паранормальные преступления.',
                                              'id': 6954,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6954-uMdvQ3Vy74Oa.png',
                                              'ru': 'Граница пустоты: Сад грешников',
                                              'score': '7.10'},
                                          {   'en': 'Record of Lodoss War',
                                              'genres': 'Классическое фэнтези',
                                              'hook': 'Золотой стандарт западного фэнтези: рыцари, эльфы и драконы в '
                                                      'борьбе со злом.',
                                              'id': 207,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx207-B2lxEFGigYgd.png',
                                              'ru': 'Летопись войн острова Лодосс',
                                              'score': '7.00'},
                                          {   'en': 'To Your Eternity',
                                              'genres': 'Фэнтези, Драма',
                                              'hook': 'Бессмертная безымянная сфера познаёт человеческие чувства '
                                                      'сквозь череду потерь.',
                                              'id': 41025,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx114535-y3NnjexcqKG1.jpg',
                                              'ru': 'Для тебя, Бессмертный',
                                              'score': '8.10'},
                                          {   'en': 'Helck',
                                              'genres': 'Фэнтези, Экшен',
                                              'hook': 'Могучий человек Хельк участвует в турнире на звание владыки '
                                                      'демонов, чтобы уничтожить людей.',
                                              'id': 51020,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx145140-tHT8TT2XSsOh.jpg',
                                              'ru': 'Хельк',
                                              'score': '7.10'},
                                          {   'en': 'Made in Abyss: Dawn of the Deep Soul',
                                              'genres': 'Фэнтези, Приключения',
                                              'hook': 'Спуск Рико и Рэга на 5-й уровень Бездны и роковое '
                                                      'противостояние с Бондрюдом.',
                                              'id': 36862,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx100643-fPH9OgEKKvcI.jpg',
                                              'ru': 'Созданный в Бездне: Рассвет души',
                                              'score': '8.50'},
                                          {   'en': 'Vinland Saga Season 2',
                                              'genres': 'Исторический, Драма',
                                              'hook': 'Торфинн проходит путь от раба и убийцы к истинному пониманию '
                                                      'ненасилия и мира.',
                                              'id': 49387,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx136430-gsBsJjA7hGh9.jpg',
                                              'ru': 'Сага о Винланде 2',
                                              'score': '8.80'},
                                          {   'en': "The Ancient Magus' Bride",
                                              'genres': 'Фэнтези, Магия',
                                              'hook': 'Сирота Чисэ Хатори обретает новый дом и магическую силу рядом с '
                                                      'нечеловеком Элиасом.',
                                              'id': 35062,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98436-n7sK6POCd0XV.png',
                                              'ru': 'Невеста чародея',
                                              'score': '7.80'},
                                          {   'en': 'Record of Grancrest War',
                                              'genres': 'Фэнтези, Экшен',
                                              'hook': 'Юный рыцарь Тео и гениальная волшебница Силука объединяют '
                                                      'расколотый войнами континент.',
                                              'id': 34279,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97768-atbPjYJNXnIo.jpg',
                                              'ru': 'Хроники войны Гранкреста',
                                              'score': '6.90'},
                                          {   'en': 'The Twelve Kingdoms',
                                              'genres': 'Классическое фэнтези',
                                              'hook': 'Школьница переносится в древний мир 12 монархий, управляемых '
                                                      'мудрыми зверями Киринами.',
                                              'id': 153,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx153-pLhZPQCYk7hl.png',
                                              'ru': 'Двенадцать королевств',
                                              'score': '7.70'},
                                          {   'en': 'Rage of Bahamut: Genesis',
                                              'genres': 'Фэнтези, Приключения',
                                              'hook': 'Дерзкий авантюрист Фаваро и беглая демоница Амира в эпическом '
                                                      'фэнтези-роуд-муви.',
                                              'id': 21843,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20590-LuMDAd75Kg3C.jpg',
                                              'ru': 'Ярость Бахамута: Генезис',
                                              'score': '7.40'},
                                          {   'en': 'Somali and the Forest Spirit',
                                              'genres': 'Фэнтези, Семейный',
                                              'hook': 'Одинокий бессердечный Голем защищает человеческую девочку в '
                                                      'мире сказочных монстров.',
                                              'id': 39575,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx108617-PgoYLgWzzm0c.png',
                                              'ru': 'Сомали и дух леса',
                                              'score': '7.60'},
                                          {   'en': 'Rokka -Braves of the Six Flowers-',
                                              'genres': 'Фэнтези, Детектив',
                                              'hook': 'Семь избранных героев собираются победить бога зла, но один из '
                                                      'них — самозванец-предатель.',
                                              'id': 28497,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20955-MeZp4OtwKGl1.jpg',
                                              'ru': 'Герои шести лепестков',
                                              'score': '7.00'},
                                          {   'en': 'Scrapped Princess',
                                              'genres': 'Фэнтези, Приключения',
                                              'hook': 'Пасифика Касулл объявлена «Ядом мира», и брат с сестрой '
                                                      'защищают ее от армий всего континента.',
                                              'id': 167,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b167-qwMN7Wmlen5s.jpg',
                                              'ru': 'Выброшенная принцесса',
                                              'score': '7.10'},
                                          {   'en': 'Lord Marksman and Vanadis',
                                              'genres': 'Фэнтези, Военный',
                                              'hook': 'Меткий лучник Тигр нанимается на службу к прекрасной деве войны '
                                                      'Элеоноре.',
                                              'id': 24455,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20809-QJQM3RI8PI4a.jpg',
                                              'ru': 'Король магических стрел и Ванадис',
                                              'score': '6.70'},
                                          {   'en': 'Chaika -The Coffin Princess-',
                                              'genres': 'Фэнтези, Экшен',
                                              'hook': 'Серебровласая волшебница с гробом за спиной собирает останки '
                                                      'отца-императора.',
                                              'id': 20853,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20462-Gi2HXG6e1oYY.jpg',
                                              'ru': 'Чайка, принцесса с гробом',
                                              'score': '6.90'},
                                          {   'en': 'GARO -VANISHING LINE-',
                                              'genres': 'Фэнтези, Экшен',
                                              'hook': 'Золотой Рыцарь Сворд и девочка Софи ищут ключ к таинственному '
                                                      'слову «Эльдорадо».',
                                              'id': 36144,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b99796-rzZSKHBRIn6E.png',
                                              'ru': 'Гаро: Линия схода',
                                              'score': '6.70'},
                                          {   'en': 'Brave Story',
                                              'genres': 'Фэнтези, Сказка',
                                              'hook': 'Мальчик Ватару входит в волшебный мир Вижен, чтобы изменить '
                                                      'судьбу своей семьи у Богини.',
                                              'id': 1681,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b1681-G12LPkws93Ub.jpg',
                                              'ru': 'Отважное сердце',
                                              'score': '7.00'}],
                        'desc': 'Магия, масштабные миры, эпические сражения и незабываемые путешествия:',
                        'key': 'epic_fantasy',
                        'name': '⚔️ Эпическое фэнтези и приключения',
                        'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101348-2fhDFPCuMNiz.jpg',
                        'shiki_genre': None,
                        'shiki_order': None,
                        'tags': '#фэнтези #приключения #эпик',
                        'title': 'Эпическое фэнтези и приключения ⚔️'},
    'hidden_gems': {   'candidates': [   {   'en': 'Shinsekai yori',
                                             'genres': 'Драма, Фантастика',
                                             'hook': 'Утопическое общество телекинетиков скрывает леденящую кровь '
                                                     'тайну.',
                                             'id': 13125,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx13125-2EDZb8ahshQc.png',
                                             'ru': 'Из нового света',
                                             'score': '8.00'},
                                         {   'en': 'Ping Pong THE ANIMATION',
                                             'genres': 'Спорт, Драма',
                                             'hook': 'Шедевр Масааки Юасы о дружбе, призвании и взрослении через '
                                                     'спорт.',
                                             'id': 22135,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20607-fIOxVISIl0HY.jpg',
                                             'ru': 'Пинг-понг',
                                             'score': '8.60'},
                                         {   'en': 'Ergo Proxy',
                                             'genres': 'Детектив, Психология',
                                             'hook': 'Загадки города-купола Ромдо, где андроиды внезапно обретают '
                                                     'душу.',
                                             'id': 790,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx790-YTUCvBKX8ZWK.jpg',
                                             'ru': 'Эрго Прокси',
                                             'score': '7.60'},
                                         {   'en': 'Kino no Tabi: the Beautiful World',
                                             'genres': 'Приключения, Философия',
                                             'hook': 'Путешественница Кино и говорящий мотоцикл исследуют обычаи стран '
                                                     'мира.',
                                             'id': 486,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx486-xXUgNOEBuxGs.jpg',
                                             'ru': 'Путешествие Кино',
                                             'score': '8.10'},
                                         {   'en': 'Baccano!',
                                             'genres': 'Экшен, Комедия',
                                             'hook': 'Вихрь мафиози, алхимиков и бессмертных на трансконтинентальном '
                                                     'поезде.',
                                             'id': 2251,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2251-tTQoWxVy4472.jpg',
                                             'ru': 'Баккано! (Шумиха)',
                                             'score': '8.10'},
                                         {   'en': 'Mononoke',
                                             'genres': 'Мистика, Детектив',
                                             'hook': 'Безымянный Аптекарь изгоняет духов, раскрывая их Форму, Суть и '
                                                     'Первопричину.',
                                             'id': 2246,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2246-WHkSkgyuxfgD.jpg',
                                             'ru': 'Мононокэ',
                                             'score': '8.20'},
                                         {   'en': 'Haibane Renmei',
                                             'genres': 'Драма, Мистика',
                                             'hook': 'Девушка с пепельными крыльями ищет свое предназначение в городе '
                                                     'за Стеной.',
                                             'id': 387,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx387-dS4aJivu0zPB.png',
                                             'ru': 'Альянс Серокрылых',
                                             'score': '8.00'},
                                         {   'en': 'RAINBOW: Nisha Rokubou no Shichinin',
                                             'genres': 'Драма, Триллер',
                                             'hook': 'Семеро юношей в колонии строгого режима находят братство посреди '
                                                     'жестокости.',
                                             'id': 6114,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b6114-pLPszMA7AxbD.jpg',
                                             'ru': 'Радуга: Семеро из шестой камеры',
                                             'score': '8.20'},
                                         {   'en': 'CLAYMORE',
                                             'genres': 'Тёмное фэнтези, Экшен',
                                             'hook': 'Воительницы с серебряными глазами очищают континент от '
                                                     'чудовищ-йома.',
                                             'id': 1818,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1818-KieLJv0qo3mO.jpg',
                                             'ru': 'Клеймор',
                                             'score': '7.40'},
                                         {   'en': 'TEXHNOLYZE',
                                             'genres': 'Киберпанк, Драма',
                                             'hook': 'Бескомпромиссная антиутопия подземного города Люкс на грани '
                                                     'угасания.',
                                             'id': 26,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx26-ADSztyHBNO39.jpg',
                                             'ru': 'Технолайз',
                                             'score': '7.60'},
                                         {   'en': 'Dororo',
                                             'genres': 'Исторический, Экшен',
                                             'hook': 'Хяккимару возвращает украденные демонами органы, истребляя '
                                                     'нечисть.',
                                             'id': 37520,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101347-TGaDwEYqLfm1.jpg',
                                             'ru': 'Дороро',
                                             'score': '8.10'},
                                         {   'en': 'Death Parade',
                                             'genres': 'Психология, Драма',
                                             'hook': 'Таинственный бар, где души умерших обнажают истинную натуру в '
                                                     'играх.',
                                             'id': 28223,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx20931-bktYqOcxPERi.jpg',
                                             'ru': 'Парад смерти',
                                             'score': '8.00'},
                                         {   'en': 'Boku dake ga Inai Machi',
                                             'genres': 'Детектив, Триллер',
                                             'hook': 'Мангака возвращается в детство, чтобы предотвратить гибель '
                                                     'девочки.',
                                             'id': 31043,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21234-XmqW39aQ9o7O.jpg',
                                             'ru': 'Город, в котором меня нет',
                                             'score': '8.10'},
                                         {   'en': 'Akatsuki no Yona',
                                             'genres': 'Приключения, Фэнтези',
                                             'hook': 'Изгнанная принцесса собирает легендарных воинов-драконов ради '
                                                     'царства.',
                                             'id': 25013,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20770-brCDvhTXlums.png',
                                             'ru': 'Рассвет Йоны',
                                             'score': '7.90'},
                                         {   'en': 'MUSHI-SHI',
                                             'genres': 'Adventure, Fantasy, Mystery',
                                             'hook': 'Медитативное философское странствие целителя духов по древней '
                                                     'Японии.',
                                             'id': 457,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx457-l6cTtNgI9Bi6.png',
                                             'ru': 'Мастер муси',
                                             'score': '8.65'},
                                         {   'en': 'Serial Experiments Lain',
                                             'genres': 'Drama, Mystery, Psychological',
                                             'hook': 'Культовое философское предсказание интернета и размытия '
                                                     'реальности.',
                                             'id': 339,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx339-xF2wp1NQuQ4r.png',
                                             'ru': 'Эксперименты Лэйн',
                                             'score': '8.1'},
                                         {   'en': 'Bakemonogatari',
                                             'genres': 'Comedy, Drama, Mystery',
                                             'hook': 'Уникальный диалоговый стиль студии Shaft о духах и '
                                                     'психологических травмах.',
                                             'id': 5081,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5081-9GocceQ5Z865.jpg',
                                             'ru': 'Истории монстров',
                                             'score': '8.32'},
                                         {   'en': 'The Tatami Galaxy',
                                             'genres': 'Comedy, Mystery, Psychological',
                                             'hook': 'Головокружительный поиск идеальной студенческой жизни во '
                                                     'временной петле.',
                                             'id': 7785,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7785-aTjIhsYva8cJ.jpg',
                                             'ru': 'Сказ о четырёх с половиной татами',
                                             'score': '8.55'},
                                         {   'en': 'Kaiba',
                                             'genres': 'Adventure, Mystery, Psychological',
                                             'hook': 'Антиутопия о мире, где воспоминания оцифрованы и продаются как '
                                                     'товар.',
                                             'id': 3701,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx3701-ooD3N9dD2rqa.jpg',
                                             'ru': 'Кайба',
                                             'score': '8.14'},
                                         {   'en': 'Sonny Boy',
                                             'genres': 'Drama, Mystery, Psychological',
                                             'hook': 'Сюрреалистичный артхаус о дрейфе школьного класса между мирами.',
                                             'id': 48849,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx132126-4ugVjXMQLAps.png',
                                             'ru': 'Сонни Бой',
                                             'score': '7.86'},
                                         {   'en': 'Showa Genroku Rakugo Shinju',
                                             'genres': 'Drama',
                                             'hook': 'Глубокая драма о традиционном японском искусстве театра одного '
                                                     'актёра.',
                                             'id': 28735,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20972-95dyLz6lkCZ8.jpg',
                                             'ru': 'Сёва-Гэнроку: Двойное самоубийство по ракуго',
                                             'score': '8.54'},
                                         {   'en': 'Great Pretender',
                                             'genres': 'Action, Comedy, Drama',
                                             'hook': 'Стильный авантюрный триллер о международных мошенниках '
                                                     'экстра-класса.',
                                             'id': 40052,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx110349-59hhZ9CNHVdk.png',
                                             'ru': 'Великий притворщик',
                                             'score': '8.19'},
                                         {   'en': 'Dorohedoro',
                                             'genres': 'Action, Adventure, Comedy',
                                             'hook': 'Гротескное тёмное фэнтези о парне с головой крокодила в мире '
                                                     'магов.',
                                             'id': 38668,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105228-I4xr84QS9Pvk.jpg',
                                             'ru': 'Дорохедоро',
                                             'score': '8.05'},
                                         {   'en': 'Land of the Lustrous',
                                             'genres': 'Action, Drama, Fantasy',
                                             'hook': 'Потрясающая 3D-эстетика о бессмертных разумных минералах и '
                                                     'потере себя.',
                                             'id': 35557,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98707-25nUKb4XUFgY.png',
                                             'ru': 'Страна самоцветов',
                                             'score': '8.39'},
                                         {   'en': 'Kemono Jihen',
                                             'genres': 'Action, Drama, Mystery',
                                             'hook': 'Атмосферный детектив о детях-полудемонах, раскрывающих '
                                                     'паранормальные тайны.',
                                             'id': 40908,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx114085-2w5rYZTOa7ER.jpg',
                                             'ru': 'Инцидент Кэмоно',
                                             'score': '7.35'},
                                         {   'en': "Vivy -Fluorite Eye's Song-",
                                             'genres': 'Action, Drama, Music',
                                             'hook': 'Андроид-певица спасает будущее человечества на протяжении 100 '
                                                     'лет.',
                                             'id': 46095,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx128546-UIwyhuhjxmL0.jpg',
                                             'ru': 'Виви: Песнь флюоритового глаза',
                                             'score': '8.37'},
                                         {   'en': 'Megalobox',
                                             'genres': 'Action, Drama, Sci-Fi',
                                             'hook': 'Драйвовая ретро-история бойца без экзоскелета, бросившего вызов '
                                                     'чемпионам.',
                                             'id': 36563,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b100298-A5VQUcw7ZC64.jpg',
                                             'ru': 'Мегалобокс',
                                             'score': '7.87'},
                                         {   'en': 'ID: INVADED',
                                             'genres': 'Drama, Mystery, Psychological',
                                             'hook': 'Гениальный сыщик погружается в подсознание серийных убийц.',
                                             'id': 40046,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx110350-uchN78wglmhN.png',
                                             'ru': 'ID: Вторжение',
                                             'score': '7.81'},
                                         {   'en': 'DECA-DENCE',
                                             'genres': 'Action, Adventure, Sci-Fi',
                                             'hook': 'Необычный постапокалипсис о летающей крепости и людях против '
                                                     'чудовищ.',
                                             'id': 40056,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx110353-XGYSsii7qJeK.png',
                                             'ru': 'Дека-данс',
                                             'score': '7.35'},
                                         {   'en': 'Katanagatari',
                                             'genres': 'Action, Adventure, Romance',
                                             'hook': 'Увлекательное странствие мечника без меча и хитрой стратегини за '
                                                     '12 клинками.',
                                             'id': 6594,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6594-xrrFyCacxUle.png',
                                             'ru': 'Истории мечей',
                                             'score': '8.29'},
                                         {   'en': 'Planetes',
                                             'genres': 'Drama, Romance, Sci-Fi',
                                             'hook': 'Научно достоверная производственная драма о космических '
                                                     'мусорщиках.',
                                             'id': 329,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx329-4xwXdazRA7Ph.png',
                                             'ru': 'Странники',
                                             'score': '8.25'},
                                         {   'en': 'Den-noh Coil',
                                             'genres': 'Adventure, Comedy, Drama',
                                             'hook': 'Школьники исследуют загадки дополненной реальности и виртуальных '
                                                     'призраков.',
                                             'id': 2164,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2164-4tUI4MJCZQO3.png',
                                             'ru': 'Кибер-виток',
                                             'score': '8.02'},
                                         {   'en': 'Penguindrum',
                                             'genres': 'Drama, Mystery, Psychological',
                                             'hook': 'Символическая притча о судьбе, семейных узах и цене спасения '
                                                     'жизни.',
                                             'id': 10721,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10721-lNEbDPX24qzn.jpg',
                                             'ru': 'Пингвиний барабан',
                                             'score': '7.92'},
                                         {   'en': 'Shiki',
                                             'genres': 'Horror, Mystery, Supernatural',
                                             'hook': 'Леденящее противостояние жителей отдаленной деревни и восставших '
                                                     'вампиров.',
                                             'id': 7724,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7724-NwNnRsI34eDa.jpg',
                                             'ru': 'Усопшие',
                                             'score': '7.72'},
                                         {   'en': 'Paranoia Agent',
                                             'genres': 'Drama, Mystery, Psychological',
                                             'hook': 'Психологический триллер Сатоси Кона о таинственном мальчике на '
                                                     'роликах.',
                                             'id': 323,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx323-ZGkUcJOn4ngy.png',
                                             'ru': 'Агент паранойи',
                                             'score': '7.66'},
                                         {   'en': 'Space Dandy',
                                             'genres': 'Comedy, Sci-Fi',
                                             'hook': 'Безумное комедийное путешествие стиляги и охотника за редкими '
                                                     'инопланетянами.',
                                             'id': 20057,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20057-tG83EpH5Gu8K.jpg',
                                             'ru': 'Космический Денди',
                                             'score': '7.89'},
                                         {   'en': "Wolf's Rain",
                                             'genres': 'Action, Adventure, Drama',
                                             'hook': 'Поэтичная постапокалиптическая элегия о поиске волками '
                                                     'потерянного Рая.',
                                             'id': 202,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx202-w2OLL3j8WmDm.jpg',
                                             'ru': 'Волчий дождь',
                                             'score': '7.79'},
                                         {   'en': 'Ghost Hound',
                                             'genres': 'Horror, Mystery, Psychological',
                                             'hook': 'Мистический психологический триллер от создателей «Лэйн» о '
                                                     'травмах детства.',
                                             'id': 2596,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2596-7VmcTkkQmOST.jpg',
                                             'ru': 'Охота на призраков',
                                             'score': '7.39'},
                                         {   'en': 'Kyousougiga',
                                             'genres': 'Фэнтези, Семейный',
                                             'hook': 'Девочка с гигантским молотом попадает в Зазеркальный Киото в '
                                                     'поисках своей матери.',
                                             'id': 10893,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10893-B511LX2N4aYm.jpg',
                                             'ru': 'Радости скорби',
                                             'score': '6.80'},
                                         {   'en': 'Humanity Has Declined',
                                             'genres': 'Комедия, Фэнтези',
                                             'hook': 'Ироничная сатира на закате человеческой эры, где новыми '
                                                     'хозяевами мира стали феи.',
                                             'id': 10357,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10357-JJvq6G2S01kl.png',
                                             'ru': 'Человечество увяло',
                                             'score': '7.50'},
                                         {   'en': 'The Heike Story',
                                             'genres': 'Исторический, Драма',
                                             'hook': 'Юная провидица становится свидетельницей падения великого '
                                                     'самурайского клана.',
                                             'id': 49738,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx138714-dLyXT5qyTYbr.jpg',
                                             'ru': 'Повесть о доме Тайра',
                                             'score': '7.70'},
                                         {   'en': 'Keep Your Hands Off Eizouken!',
                                             'genres': 'Комедия, Повседневность',
                                             'hook': 'Три увлечённые школьницы создают собственный независимый '
                                                     'аниме-шедевр.',
                                             'id': 39792,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx109298-suwdIUbJEPJx.png',
                                             'ru': 'Руки прочь от кинокружка!',
                                             'score': '8.00'},
                                         {   'en': 'Ranking of Kings',
                                             'genres': 'Фэнтези, Приключения',
                                             'hook': 'Глухонемой слабый принц Бодзи доказывает миру, что храброе '
                                                     'сердце сильнее любого меча.',
                                             'id': 40834,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113717-9sNnN8WRgK15.jpg',
                                             'ru': 'Рейтинг короля',
                                             'score': '8.30'},
                                         {   'en': 'ACCA: 13-Territory Inspection Dept.',
                                             'genres': 'Детектив, Драма',
                                             'hook': 'Невозмутимый чиновник расследует слухи о государственном '
                                                     'перевороте за чашкой чая.',
                                             'id': 33337,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21823-0XTjZ0Rtm7va.jpg',
                                             'ru': 'АККА: Инспекция по 13 округам',
                                             'score': '7.50'},
                                         {   'en': 'Barakamon',
                                             'genres': 'Комедия, Повседневность',
                                             'hook': 'Вспыльчивый каллиграф отправляется на сельский остров и учится '
                                                     'радоваться простым мелочам.',
                                             'id': 22789,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20722-2KAeq72E95dr.png',
                                             'ru': 'Баракамон',
                                             'score': '8.20'},
                                         {   'en': 'Bunny Drop',
                                             'genres': 'Повседневность, Семейный',
                                             'hook': '30-летний холостяк берёт на воспитание внебрачную дочь своего '
                                                     'покойного дедушки.',
                                             'id': 10162,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10162-w4SG5oQSQwMn.jpg',
                                             'ru': 'Брошенный кролик',
                                             'score': '8.10'},
                                         {   'en': 'Silver Spoon',
                                             'genres': 'Повседневность, Комедия',
                                             'hook': 'Городской отличник сбегает от ожиданий семьи в строгую '
                                                     'сельскохозяйственную школу.',
                                             'id': 16918,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16918-0biAxYFR29mw.png',
                                             'ru': 'Серебряная ложка',
                                             'score': '7.90'},
                                         {   'en': 'Natsume Yuujinchou × Kumamoto-ken: Hitoyoshi Kuma de no Yasashii '
                                                   'Jikan',
                                             'genres': 'Мистика, Повседневность',
                                             'hook': 'Одинокий юноша возвращает имена духам, записанным в '
                                                     'наследственной тетради бабушки.',
                                             'id': 48953,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b188619-zBWxqUo3oWXo.png',
                                             'ru': 'Тетрадь дружбы Нацумэ',
                                             'score': '6.60'},
                                         {   'en': 'MEGALOBOX 2: NOMAD',
                                             'genres': 'Спорт, Драма',
                                             'hook': 'Постаревший и потерянный боксёр возвращается на ринг ради '
                                                     'искупления грехов прошлого.',
                                             'id': 40729,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113359-FnjG2VppJF9f.png',
                                             'ru': 'Мегалобокс 2: Кочевник',
                                             'score': '8.10'},
                                         {   'en': 'Kemonozume',
                                             'genres': 'Экшен, Романтика',
                                             'hook': 'Охотник на чудовищ влюбляется в девушку, способную превращаться '
                                                     'в плотоядного монстра.',
                                             'id': 1454,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1454-fyg2zIQz5Qsj.png',
                                             'ru': 'Когти зверя',
                                             'score': '7.10'},
                                         {   'en': 'Erin',
                                             'genres': 'Фэнтези, Драма',
                                             'hook': 'Трогательная история девочки, научившейся понимать язык '
                                                     'опаснейших боевых ящеров.',
                                             'id': 5420,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5420-hOjyV2QC1yIG.jpg',
                                             'ru': 'Эрин, заклинательница зверей',
                                             'score': '8.00'},
                                         {   'en': 'Gankutsuou: The Count of Monte Cristo',
                                             'genres': 'Детектив, Sci-Fi',
                                             'hook': 'Уникальная визуальная стилистика романа Дюма в футуристическом '
                                                     'космическом Париже.',
                                             'id': 239,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx239-eldiiZxky1Ul.png',
                                             'ru': 'Граф Монте-Кристо',
                                             'score': '7.90'},
                                         {   'en': 'Princess Tutu',
                                             'genres': 'Сказка, Махо-сёдзё',
                                             'hook': 'Маленькая утка превращается в девочку-балерину, чтобы собрать '
                                                     'осколки сердца принца.',
                                             'id': 721,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx721-9tJpM47RBPJm.jpg',
                                             'ru': 'Принцесса Тютю',
                                             'score': '8.10'},
                                         {   'en': "Welcome to Irabu's Office",
                                             'genres': 'Психология, Комедия',
                                             'hook': 'Эксцентричный психиатр Ирабу лечит неврозы пациентов самыми '
                                                     'безумными методами.',
                                             'id': 6774,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6774-9yybYg3VePJU.png',
                                             'ru': 'Трапеция',
                                             'score': '7.60'},
                                         {   'en': 'SHADOWS HOUSE',
                                             'genres': 'Мистика, Детектив',
                                             'hook': 'Живые куклы прислуживают безликим аристократам-теням в особняке, '
                                                     'полном мрачных тайн.',
                                             'id': 43439,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx125038-BCfEvry0QBXW.png',
                                             'ru': 'Дом теней',
                                             'score': '7.70'},
                                         {   'en': 'Hanasaku Iroha ~Blossoms for Tomorrow~',
                                             'genres': 'Повседневность, Драма',
                                             'hook': '16-летняя Охана работает горничной в традиционной гостинице на '
                                                     'горячих источниках.',
                                             'id': 9289,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx9289-2Y14iZ2pMqeX.jpg',
                                             'ru': 'Азбука цветов',
                                             'score': '7.70'},
                                         {   'en': 'Flying Witch',
                                             'genres': 'Повседневность, Магия',
                                             'hook': 'Юная ведьма Макото переезжает к родственникам в деревню и '
                                                     'постигает тихую магию природы.',
                                             'id': 31376,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21284-vQcCLIWt1o5O.png',
                                             'ru': 'Полёт ведьмы',
                                             'score': '7.40'},
                                         {   'en': 'Tari Tari',
                                             'genres': 'Повседневность, Музыка',
                                             'hook': 'Пятеро непохожих старшеклассников объединяются в клуб хорового '
                                                     'пения.',
                                             'id': 13333,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx13333-yDRfFOMbrbf0.png',
                                             'ru': 'Тари Тари',
                                             'score': '7.00'},
                                         {   'en': 'Tamako Market',
                                             'genres': 'Повседневность, Комедия',
                                             'hook': 'Дочь торговца моти Тамако и говорящая птица Дзерамоти в торговом '
                                                     'квартале Усагияма.',
                                             'id': 16417,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx16417-r8Njy5UnwvDE.png',
                                             'ru': 'Лавочка Тамако',
                                             'score': '7.30'},
                                         {   'en': 'The Eccentric Family',
                                             'genres': 'Фэнтези, Комедия',
                                             'hook': 'Семья оборотней-тануки в Киото балансирует между летающими тэнгу '
                                                     'и клубом гурманов Пятницы.',
                                             'id': 17909,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx17909-BXyd04Lj8F6M.jpg',
                                             'ru': 'Эксцентричное семейство',
                                             'score': '7.70'}],
                       'desc': 'Редкие находки с великолепным сюжетом, незаслуженно оставшиеся в тени хайпа:',
                       'key': 'hidden_gems',
                       'name': '💎 Недооценённые алмазы и скрытые жемчужины',
                       'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx13125-2EDZb8ahshQc.png',
                       'shiki_genre': None,
                       'shiki_order': None,
                       'tags': '#hidden_gems #недооцененное #чтопосмотреть',
                       'title': 'Недооценённые алмазы и скрытые шедевры 💎'},
    'isekai_special': {   'candidates': [   {   'en': 'Mushoku Tensei: Isekai Ittara Honki Dasu',
                                                'genres': 'Магия, Приключения',
                                                'hook': '34-летний затворник получает второй шанс прожить достойную '
                                                        'жизнь с мечом и магией.',
                                                'id': 39535,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx108465-1ANspF1EWyFx.jpg',
                                                'ru': 'Реинкарнация безработного',
                                                'score': '8.20'},
                                            {   'en': 'Re:Zero kara Hajimeru Isekai Seikatsu',
                                                'genres': 'Триллер, Драма',
                                                'hook': 'Субару Нацуки обретает способность возвращаться во времени '
                                                        'только после гибели.',
                                                'id': 31240,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21355-wRVUrGxpvIQQ.jpg',
                                                'ru': 'Re:Zero — жизнь с нуля в другом мире',
                                                'score': '8.10'},
                                            {   'en': 'Tensei Shitara Slime Datta Ken',
                                                'genres': 'Фэнтези, Сёнэн',
                                                'hook': 'Офисный клерк перерождается слизью и строит процветающую '
                                                        'федерацию монстров.',
                                                'id': 37430,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101280-tDxCVJm714nt.jpg',
                                                'ru': 'О моём перерождении в слизь',
                                                'score': '8.00'},
                                            {   'en': 'Overlord',
                                                'genres': 'Фэнтези, Экшен',
                                                'hook': 'Геймер остается заперт в теле могущественного скелета-мага в '
                                                        'новом мире.',
                                                'id': 29803,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20832-vUNm5zrYWifc.jpg',
                                                'ru': 'Повелитель (Overlord)',
                                                'score': '7.70'},
                                            {   'en': 'Tate no Yuusha no Nariagari',
                                                'genres': 'Драма, Фэнтези',
                                                'hook': 'Оболганный и преданный герой щита поднимается со дна ради '
                                                        'справедливости.',
                                                'id': 35790,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99263-LcazQwdlWzMy.jpg',
                                                'ru': 'Восхождение героя щита',
                                                'score': '7.60'},
                                            {   'en': 'Youjo Senki',
                                                'genres': 'Магия, Военное',
                                                'hook': 'Циничный японский менеджер перерождается одаренной '
                                                        'девочкой-магом на войне.',
                                                'id': 32615,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21613-qT3NiwYP5dYc.png',
                                                'ru': 'Военная хроника маленькой девочки',
                                                'score': '7.80'},
                                            {   'en': 'No Game No Life',
                                                'genres': 'Игры, Комедия',
                                                'hook': 'Гениальные брат и сестра попадают в мир, где любые конфликты '
                                                        'решаются играми.',
                                                'id': 19815,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b19815-sEOQ9yQaPKlk.jpg',
                                                'ru': 'Нет игры — нет жизни',
                                                'score': '7.70'},
                                            {   'en': 'Kumo desu ga, Nani ka?',
                                                'genres': 'Экшен, Фэнтези',
                                                'hook': 'Обычная школьница перерождается слабейшим паучком в '
                                                        'смертоносном лабиринте.',
                                                'id': 37984,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx103632-2wsy9wFUdm1C.jpg',
                                                'ru': 'Да, я паук, и что же?',
                                                'score': '7.20'},
                                            {   'en': 'Maou Gakuin no Futekigousha: Shijou Saikyou no Maou no Shiso, '
                                                      'Tensei shite Shison-tachi no Gakkou e Kayou',
                                                'genres': 'Магия, Фэнтези',
                                                'hook': 'Всемогущий владыка демонов перерождается спустя 2000 лет в '
                                                        'мирной эпохе.',
                                                'id': 40496,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx112301-f88Fs2es4pSr.jpg',
                                                'ru': 'Непризнанный школой владыка демонов',
                                                'score': '7.20'},
                                            {   'en': 'Shinchou Yuusha: Kono Yuusha ga Ore TUEEE Kuse ni Shinchou '
                                                      'Sugiru',
                                                'genres': 'Комедия, Фэнтези',
                                                'hook': 'Богиня призывает невероятно сильного героя, который '
                                                        'перестраховывается во всем.',
                                                'id': 38659,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105156-ZVtxISdoUqnY.png',
                                                'ru': 'Этот герой неуязвим, но очень осторожен',
                                                'score': '7.30'},
                                            {   'en': 'Tensei Shitara Ken Deshita',
                                                'genres': 'Экшен, Фэнтези',
                                                'hook': 'Разумный меч становится наставником и оружием юной '
                                                        'кошкодевочки Фран.',
                                                'id': 49891,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx139587-rbZVcigCRtHY.jpg',
                                                'ru': 'О моём перерождении в меч',
                                                'score': '7.40'},
                                            {   'en': 'Hai to Gensou no Grimgar',
                                                'genres': 'Драма, Фэнтези',
                                                'hook': 'Группа новичков без воспоминаний отчаянно учится выживать в '
                                                        'суровом мире.',
                                                'id': 31859,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21428-dFVIHeZ8McBe.jpg',
                                                'ru': 'Гримгал пепла и иллюзий',
                                                'score': '7.40'},
                                            {   'en': 'Log Horizon',
                                                'genres': 'Action, Adventure, Fantasy',
                                                'hook': 'Тысячи игроков заперты в MMORPG и строят цивилизацию силой '
                                                        'стратегии и экономики.',
                                                'id': 17265,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx17265-RyErURYesjJt.jpg',
                                                'ru': 'Покорение горизонта',
                                                'score': '7.89'},
                                            {   'en': 'DRIFTERS OVA',
                                                'genres': 'Action, Adventure, Comedy',
                                                'hook': 'Легендарные полководцы Земли призваны в фэнтези-мир для '
                                                        'эпической тотальной войны.',
                                                'id': 36480,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97988-rq6xyZPj25Ao.jpg',
                                                'ru': 'Скитальцы OVA',
                                                'score': '7.52'},
                                            {   'en': 'Gate',
                                                'genres': 'Action, Adventure, Fantasy',
                                                'hook': 'Современная армия Японии с танками и авиацией исследует мир '
                                                        'магии и драконов.',
                                                'id': 28907,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20994-pSDk4I58jAK5.jpg',
                                                'ru': 'Врата: Там бьются наши воины',
                                                'score': '7.67'},
                                            {   'en': 'Ascendance of a Bookworm: Adopted Daughter of an Archduke',
                                                'genres': 'Drama, Fantasy, Slice of Life',
                                                'hook': 'Погибшая библиотекарша перерождается в бедной семье и '
                                                        'воссоздает печать книг.',
                                                'id': 57466,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx171110-7zOdInS6DQNL.jpg',
                                                'ru': 'Власть книжного червя: Приёмная дочь лорда',
                                                'score': '7.76'},
                                            {   'en': 'TSUKIMICHI -Moonlit Fantasy-',
                                                'genres': 'Action, Adventure, Comedy',
                                                'hook': 'Отвергнутый богиней за внешность герой строит общество '
                                                        'монстров.',
                                                'id': 43523,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx125206-O2MsOWdW1lVi.jpg',
                                                'ru': 'Лунное путешествие приведёт к новому миру',
                                                'score': '7.71'},
                                            {   'en': "The World's Finest Assassin Gets Reincarnated in Another World "
                                                      'as an Aristocrat',
                                                'genres': 'Action, Adventure, Drama',
                                                'hook': 'Величайший киллер перерождается дворянином, чтобы устранить '
                                                        'Героя ради спасения мира.',
                                                'id': 47790,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx129898-FRUzDtPhRigt.jpg',
                                                'ru': 'Лучший в мире ассасин, переродившийся в другом мире как '
                                                      'аристократ',
                                                'score': '7.3'},
                                            {   'en': 'The Faraway Paladin',
                                                'genres': 'Action, Adventure, Fantasy',
                                                'hook': 'Мальчик выращен тремя неживыми героями и принимает обет '
                                                        'служения богине света.',
                                                'id': 48761,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx132473-L64hP24nJyEV.jpg',
                                                'ru': 'Далёкий паладин',
                                                'score': '6.89'},
                                            {   'en': 'Campfire Cooking in Another World with my Absurd Skill',
                                                'genres': 'Adventure, Comedy, Fantasy',
                                                'hook': 'Герой с навыком онлайн-супермаркета приручает легендарного '
                                                        'волка вкусной едой.',
                                                'id': 53446,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx156067-Jovklss4VWIx.jpg',
                                                'ru': 'Кулинарные скитания в параллельном мире',
                                                'score': '7.63'},
                                            {   'en': 'Skeleton Knight in Another World',
                                                'genres': 'Action, Adventure, Comedy',
                                                'hook': 'Геймер просыпается в доспехах своего аватара-скелета и '
                                                        'помогает угнетенным.',
                                                'id': 48760,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx132474-J2ECHSPkfb9g.jpg',
                                                'ru': 'Рыцарь-скелет вступает в параллельный мир',
                                                'score': '7.13'},
                                            {   'en': 'Trapped in a Dating Sim: The World of Otome Games Is Tough for '
                                                      'Mobs',
                                                'genres': 'Action, Fantasy, Mecha',
                                                'hook': 'Парень перерождается второстепенным персонажем и бросает '
                                                        'вызов надменной знати.',
                                                'id': 50461,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx142074-pHe4bX791PJh.jpg',
                                                'ru': 'Мир отомэ-игр — это тяжёлый мир для мобов',
                                                'score': '7.31'},
                                            {   'en': 'Uncle from Another World',
                                                'genres': 'Adventure, Comedy, Fantasy',
                                                'hook': 'Дядя выходит из 17-летней комы после исекая, поражая '
                                                        'племянника магией и видеоиграми Sega.',
                                                'id': 49220,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx135806-uhqZSNTYZe04.jpg',
                                                'ru': 'Перерождение Дяди',
                                                'score': '7.74'},
                                            {   'en': "Knight's & Magic",
                                                'genres': 'Action, Fantasy, Mecha',
                                                'hook': 'Гениальный программист-меха-отаку строит гигантских боевых '
                                                        'роботов в новом мире.',
                                                'id': 34104,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97663-4TMJDIpm3toz.png',
                                                'ru': 'Рыцари и магия',
                                                'score': '7.07'},
                                            {   'en': 'How a Realist Hero Rebuilt the Kingdom',
                                                'genres': 'Action, Adventure, Fantasy',
                                                'hook': 'Попаданец спасает страну от кризиса не мечом, а экономикой и '
                                                        'реформами.',
                                                'id': 41710,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx117612-MCbAaq2ypJlp.jpg',
                                                'ru': 'Герой-рационал перестраивает королевство',
                                                'score': '7.25'},
                                            {   'en': 'Restaurant to Another World',
                                                'genres': 'Fantasy, Slice of Life',
                                                'hook': 'Дверь токийского ресторана раз в неделю открывается для '
                                                        'эльфов, драконов и магов.',
                                                'id': 34012,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx97617-TmRRraupfbT5.jpg',
                                                'ru': 'Кафе из другого мира',
                                                'score': '7.42'},
                                            {   'en': 'Isekai Quartet',
                                                'genres': 'Comedy, Fantasy, Slice of Life',
                                                'hook': 'Чиби-кроссовер с героями Konosuba, Re:Zero, Overlord и Tanya '
                                                        'the Evil.',
                                                'id': 38472,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx104454-pH5YCR7HteqP.jpg',
                                                'ru': 'Квартет из альтернативного мира',
                                                'score': '7.37'},
                                            {   'en': 'Kemono Michi: Rise Up',
                                                'genres': 'Comedy, Fantasy, Slice of Life',
                                                'hook': 'Профессиональный рестлер переносится в фэнтези-мир и '
                                                        'открывает приют для монстров.',
                                                'id': 39030,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx107339-3mKBCMAUN896.png',
                                                'ru': 'За дело! «Звериная тропа»',
                                                'score': '6.59'},
                                            {   'en': 'By the Grace of the Gods',
                                                'genres': 'Adventure, Fantasy, Slice of Life',
                                                'hook': 'Уставший клерк перерождается ребенком и ведет мирную жизнь в '
                                                        'окружении прирученных слизней.',
                                                'id': 41312,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx115740-IRwSQo96Qs2Q.jpg',
                                                'ru': 'Избранный богами',
                                                'score': '6.95'},
                                            {   'en': 'Welcome to Demon School! Iruma-kun',
                                                'genres': 'Comedy, Fantasy',
                                                'hook': 'Добрый парень продан родителями демону и становится самым '
                                                        'популярным учеником школы ада.',
                                                'id': 39196,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx107693-A9bSSFAMxA6j.jpg',
                                                'ru': 'Добро пожаловать в ад, Ирума!',
                                                'score': '7.74'},
                                            {   'en': "Problem Children Are Coming From Another World, Aren't They?",
                                                'genres': 'Action, Comedy, Fantasy',
                                                'hook': 'Трое одаренных подростков призваны в мир «Цветущего сада» для '
                                                        'игр богов.',
                                                'id': 15315,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx15315-mvKPcy8Z2QkB.jpg',
                                                'ru': 'Проблемные дети приходят из иного мира, верно?',
                                                'score': '7.4'},
                                            {   'en': 'The Eminence in Shadow',
                                                'genres': 'Исекай, Экшен',
                                                'hook': 'Парень играет в теневого владыку, не подозревая, что все его '
                                                        'выдумки реальны.',
                                                'id': 48316,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx130298-YMdcKHytpWNH.jpg',
                                                'ru': 'Восхождение в тени',
                                                'score': '8.10'},
                                            {   'en': 'Shangri-La Frontier',
                                                'genres': 'Игры, Экшен',
                                                'hook': 'Хардкорный любитель треш-игр покоряет эталонную VR-MMORPG в '
                                                        'птичьей маске.',
                                                'id': 52347,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx151970-xtIx3VqEk02X.jpg',
                                                'ru': 'Рубеж Шангри-Ла',
                                                'score': '8.00'},
                                            {   'en': 'Chiyu Mahou no Machigatta Tsukaikata',
                                                'genres': 'Исекай, Экшен',
                                                'hook': 'Случайно призванный парень попадает в адскую спасательную '
                                                        'команду Розы.',
                                                'id': 48233,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                                'ru': 'Неправильный способ использования исцеляющей магии',
                                                'score': '7.60'},
                                            {   'en': 'Paripi Koumei',
                                                'genres': 'Реверс-исекай, Музыка',
                                                'hook': 'Легендарный древнекитайский полководец становится продюсером '
                                                        'начинающей певицы в Сибуе.',
                                                'id': 96649,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                                'ru': 'Тусовщик Кунмин',
                                                'score': '8.10'},
                                            {   'en': 'DRIFTERS',
                                                'genres': 'Исекай, Тёмное фэнтези',
                                                'hook': 'Великие воины разных исторических эпох сходятся в кровавой '
                                                        'битве за фэнтези-мир.',
                                                'id': 31339,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21123-bCuqm8wLDqOw.png',
                                                'ru': 'Скитальцы',
                                                'score': '7.50'},
                                            {   'en': 'The Devil is a Part-Timer!',
                                                'genres': 'Реверс-исекай, Комедия',
                                                'hook': 'Владыка тьмы теряет магию в Токио и устраивается жарить '
                                                        'бургеры в фастфуд.',
                                                'id': 15809,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx15809-ECv3HyOYJKrk.jpg',
                                                'ru': 'Сатана на подработке!',
                                                'score': '7.50'},
                                            {   'en': 'Parallel World Pharmacy',
                                                'genres': 'Исекай, Фэнтези',
                                                'hook': 'Погибший от переработок учёный открывает современную аптеку '
                                                        'для простолюдинов.',
                                                'id': 49438,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx136707-StRFbEwZT7q5.jpg',
                                                'ru': 'Фармацевт из параллельного мира',
                                                'score': '7.20'},
                                            {   'en': 'Farming Life in Another World',
                                                'genres': 'Исекай, Повседневность',
                                                'hook': 'Бывший клерк с божественным инструментом строит безмятежную '
                                                        'деревню мечты.',
                                                'id': 51462,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx146850-xfeAFIE0M9hl.jpg',
                                                'ru': 'Фермерская жизнь в ином мире',
                                                'score': '7.40'},
                                            {   'en': 'Ascendance of a Bookworm Side Story',
                                                'genres': 'Исекай, Повседневность',
                                                'hook': 'Погибшая библиотекарша возрождается больной девочкой Майн и '
                                                        'создает книги с нуля.',
                                                'id': 40841,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113811-DxnS7eOL5zfn.jpg',
                                                'ru': 'Власть книжного червя',
                                                'score': '7.40'},
                                            {   'en': 'Seirei Gensouki: Spirit Chronicles',
                                                'genres': 'Исекай, Фэнтези',
                                                'hook': 'Сирота Рио вспоминает прошлую жизнь японского студента и '
                                                        'обретает силу духа.',
                                                'id': 44203,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx126546-Jujx9OvKxLzA.jpg',
                                                'ru': 'Хроники мифического духа',
                                                'score': '6.90'},
                                            {   'en': 'Wise Man’s Grandchild',
                                                'genres': 'Исекай, Магия',
                                                'hook': 'Перерожденного парня вырастил легендарный Мерлин, но забыл '
                                                        'научить здравому смыслу.',
                                                'id': 36407,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx100112-eExFpnYG2QAK.jpg',
                                                'ru': 'Внук мудреца',
                                                'score': '6.40'},
                                            {   'en': 'Isekai Cheat Magician',
                                                'genres': 'Исекай, Экшен',
                                                'hook': 'Обычные школьники призываются в фэнтези-мир с богоподобным '
                                                        'запасом маны.',
                                                'id': 37744,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101547-Y0uARlMRaARP.jpg',
                                                'ru': 'Маг-обманщик из другого мира',
                                                'score': '5.20'},
                                            {   'en': "BOFURI: I Don't Want to Get Hurt, so I'll Max Out My Defense.",
                                                'genres': 'Игры, Комедия',
                                                'hook': 'Девушка Мэйпл делает билд на чистую защиту и становится '
                                                        'несокрушимым боссом игры.',
                                                'id': 38790,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx106479-JmPk1F5ubMtm.png',
                                                'ru': 'Не люблю боль, поэтому вкачаю всё в защиту',
                                                'score': '7.30'},
                                            {   'en': 'Death March to the Parallel World Rhapsody',
                                                'genres': 'Исекай, Фэнтези',
                                                'hook': '29-летний программист засыпает на работе и просыпается '
                                                        'суперсильным метеоритным магом Сато.',
                                                'id': 34497,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97907-MAOO4oDANGXm.png',
                                                'ru': 'Марш смерти в параллельный мир',
                                                'score': '6.10'},
                                            {   'en': 'In Another World With My Smartphone',
                                                'genres': 'Исекай, Гарем',
                                                'hook': 'Бог случайно убивает парня молнией, воскрешает в магии и '
                                                        'оставляет ему рабочий смартфон.',
                                                'id': 35203,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx98491-5vyX89aabiHz.jpg',
                                                'ru': 'В другом мире со смартфоном',
                                                'score': '5.70'},
                                            {   'en': 'How NOT to Summon a Demon Lord',
                                                'genres': 'Исекай, Этти',
                                                'hook': 'Замкнутый геймер переносится в аватаре демона Диабло и '
                                                        'подчиняет призвавших его рабынь.',
                                                'id': 37210,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101004-rJLBIWGypbYK.png',
                                                'ru': 'Повелитель тьмы из другого мира',
                                                'score': '6.60'},
                                            {   'en': 'Isekai Shokudou 2',
                                                'genres': 'Исекай, Кулинария',
                                                'hook': 'Дверь в западный токийский ресторан по субботам открывается '
                                                        'для эльфов, магов и драконов.',
                                                'id': 34561,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx132806-fuOSzS2YOpIt.jpg',
                                                'ru': 'В другом мире с необходимыми навыками',
                                                'score': '7.40'},
                                            {   'en': 'Cheat Pharmacist’s Slow Life',
                                                'genres': 'Исекай, Повседневность',
                                                'hook': 'Бывший офисный работник варит чудодейственные зелья в '
                                                        'собственной уютной аптеке.',
                                                'id': 47160,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx114302-xfqGNUaK59lQ.jpg',
                                                'ru': 'Фармацевт из другого мира: Неспешная жизнь',
                                                'score': '6.40'},
                                            {   'en': 'Hai to Gensou no Grimgar: Starlight',
                                                'genres': 'Фэнтези, Исекай',
                                                'hook': 'Подростки без памяти о прошлом учатся выживать и сражаться за '
                                                        'каждый кусок хлеба.',
                                                'id': 37430,
                                                'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21428-dFVIHeZ8McBe.jpg',
                                                'ru': 'Гримгал пепла и иллюзий: OVA',
                                                'score': '7.50'}],
                          'desc': 'Попаданцы в другие миры, где всё пошло не по стандартному сценарию:',
                          'key': 'isekai_special',
                          'name': '🌀 Захватывающие исекаи и попаданцы',
                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx108465-1ANspF1EWyFx.jpg',
                          'shiki_genre': None,
                          'shiki_order': None,
                          'tags': '#исекай #фэнтези #приключения',
                          'title': 'Захватывающие исекаи и попаданцы 🌀'},
    'mindfuck': {   'candidates': [   {   'en': 'DEATH NOTE',
                                          'genres': 'Мистика, Детектив',
                                          'hook': 'Интеллектуальная дуэль школьника с тетрадью смерти и гениального '
                                                  'сыщика L.',
                                          'id': 1535,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1535-kUgkcrfOrkUM.jpg',
                                          'ru': 'Тетрадь смерти',
                                          'score': '8.40'},
                                      {   'en': 'Monster',
                                          'genres': 'Драма, Триллер',
                                          'hook': 'Гениальный хирург спасает жизнь мальчику, не зная, что взрастил '
                                                  'зло.',
                                          'id': 61629,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx19-gtMC64182sm4.jpg',
                                          'ru': 'Монстр',
                                          'score': '8.80'},
                                      {   'en': 'PSYCHO-PASS',
                                          'genres': 'Детектив, Триллер',
                                          'hook': 'Система «Сивилла» вычисляет вероятность преступления еще до его '
                                                  'совершения.',
                                          'id': 13601,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx13601-i42VFuHpqEOJ.jpg',
                                          'ru': 'Психопаспорт',
                                          'score': '8.10'},
                                      {   'en': 'Kiseijuu: Sei no Kakuritsu',
                                          'genres': 'Экшен, Ужасы',
                                          'hook': 'Инопланетный паразит в руке школьника втягивает его в войну за '
                                                  'выживание.',
                                          'id': 22535,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20623-dUARfggnNDOe.jpg',
                                          'ru': 'Паразит: Учение о жизни',
                                          'score': '8.10'},
                                      {   'en': 'PERFECT BLUE',
                                          'genres': 'Психология, Триллер',
                                          'hook': 'Бывшая поп-идол теряет грань между реальностью и безумием из-за '
                                                  'сталкера.',
                                          'id': 437,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx437-69NMlXKFeuse.jpg',
                                          'ru': 'Идеальная грусть',
                                          'score': '8.50'},
                                      {   'en': 'Yakusoku no Neverland',
                                          'genres': 'Мистика, Триллер',
                                          'hook': 'Дети в идиллическом приюте узнают, что их растят на убой для '
                                                  'монстров.',
                                          'id': 37779,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101759-8UR7r9MNVpz2.jpg',
                                          'ru': 'Обещанный Неверленд',
                                          'score': '8.30'},
                                      {   'en': 'Tokyo Ghoul',
                                          'genres': 'Ужасы, Драма',
                                          'hook': 'Студент становится полугулем и балансирует между миром людей и '
                                                  'чудовищ.',
                                          'id': 22319,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b20605-k665mVkSug8D.jpg',
                                          'ru': 'Токийский гуль',
                                          'score': '7.60'},
                                      {   'en': 'Another',
                                          'genres': 'Мистика, Ужасы',
                                          'hook': 'В классе 3-3 оживает проклятие, и ученики начинают погибать один за '
                                                  'другим.',
                                          'id': 11111,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11111-gvvE5bBYsyFo.png',
                                          'ru': 'Иная',
                                          'score': '7.10'},
                                      {   'en': 'Tomodachi Game',
                                          'genres': 'Психология, Игры',
                                          'hook': 'Пятеро друзей попадают в жестокую психологическую игру ради выплаты '
                                                  'долга.',
                                          'id': 50273,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx141014-bTWr7TtS0wt9.jpg',
                                          'ru': 'Игра друзей',
                                          'score': '7.60'},
                                      {   'en': 'Charlotte',
                                          'genres': 'Драма, Сверхъестественное',
                                          'hook': 'Подростки со скрытыми способностями сталкиваются с суровой ценой '
                                                  'своих сил.',
                                          'id': 28999,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20997-axVYrsIfjtYJ.jpg',
                                          'ru': 'Шарлотта',
                                          'score': '7.50'},
                                      {   'en': 'Yahari Ore no Seishun Love Come wa Machigatteiru. Zoku: Kitto, '
                                                'Onnanoko wa Osatou to Spice to Suteki na Nanika de Dekiteiru',
                                          'genres': 'Драма, Психология',
                                          'hook': 'Циничный школьник Хатиман препарирует социальные маски сверстников.',
                                          'id': 33161,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21769-ZBoT6szJKGZv.jpg',
                                          'ru': 'Как и ожидалось, моя школьная жизнь не задалась',
                                          'score': '7.80'},
                                      {   'en': 'Sidonia no Kishi',
                                          'genres': 'Фантастика, Меха',
                                          'hook': 'Остатки человечества в космосе ведут отчаянную борьбу против '
                                                  'пришельцев-гауна.',
                                          'id': 19775,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx19775-h4Fc1q5qsGfP.png',
                                          'ru': 'Рыцари Сидонии',
                                          'score': '7.30'},
                                      {   'en': 'Classroom of the Elite',
                                          'genres': 'Drama, Psychological',
                                          'hook': 'Хладнокровный гений ведёт тайную войну умов в элитной школе.',
                                          'id': 35507,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98659-WNyPLIZDpGGY.jpg',
                                          'ru': 'Добро пожаловать в класс превосходства',
                                          'score': '7.82'},
                                      {   'en': 'The Future Diary',
                                          'genres': 'Action, Horror, Mystery',
                                          'hook': 'Смертельная королевская битва владельцев дневников, предсказывающих '
                                                  'будущее.',
                                          'id': 10620,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10620-dUZeNej0W4QN.png',
                                          'ru': 'Дневник будущего',
                                          'score': '7.38'},
                                      {   'en': 'Terror in Resonance',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Два гениальных подростка бросают вызов полиции Токио сложнейшими '
                                                  'загадками.',
                                          'id': 23283,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20661-aCR7QgzDfOSI.png',
                                          'ru': 'Эхо террора',
                                          'score': '8.08'},
                                      {   'en': 'Serial Experiments Lain',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Культовое погружение в Сеть и растворение границ между разумом и '
                                                  'кодом.',
                                          'id': 339,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx339-xF2wp1NQuQ4r.png',
                                          'ru': 'Эксперименты Лэйн',
                                          'score': '8.1'},
                                      {   'en': 'Paranoia Agent',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Детективы пытаются поймать призрачного маньяка, материализующего '
                                                  'людские страхи.',
                                          'id': 323,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx323-ZGkUcJOn4ngy.png',
                                          'ru': 'Агент паранойи',
                                          'score': '7.66'},
                                      {   'en': 'Paprika',
                                          'genres': 'Fantasy, Mystery, Psychological',
                                          'hook': 'Сюрреалистический шедевр Сатоси Кона о проникновении преступников в '
                                                  'чужие сны.',
                                          'id': 1943,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b1943-jMCEYL1Ixmgc.png',
                                          'ru': 'Паприка',
                                          'score': '8.05'},
                                      {   'en': 'ERASED',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Герой возвращается в детство, чтобы поймать серийного похитителя '
                                                  'детей.',
                                          'id': 31043,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21234-XmqW39aQ9o7O.jpg',
                                          'ru': 'Город, в котором меня нет',
                                          'score': '8.31'},
                                      {   'en': 'Re:ZERO -Starting Life in Another World-',
                                          'genres': 'Action, Adventure, Drama',
                                          'hook': 'Субару ищет путь сквозь бесконечные смерти и ментальные травмы.',
                                          'id': 31240,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21355-wRVUrGxpvIQQ.jpg',
                                          'ru': 'Re:Zero. Жизнь с нуля в альтернативном мире',
                                          'score': '8.25'},
                                      {   'en': 'Talentless Nana',
                                          'genres': 'Drama, Horror, Mystery',
                                          'hook': 'В закрытой школе для одарённых подростков появляется хитрый убийца '
                                                  'под прикрытием.',
                                          'id': 41619,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx117343-NgCLZTaxallv.jpg',
                                          'ru': 'Бездарная Нана',
                                          'score': '7.17'},
                                      {   'en': 'ID: INVADED',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Погружение в колодцы разума убийц для раскрытия изощрённых '
                                                  'преступлений.',
                                          'id': 40046,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx110350-uchN78wglmhN.png',
                                          'ru': 'ID: Вторжение',
                                          'score': '7.81'},
                                      {   'en': 'Summer Time Rendering',
                                          'genres': 'Action, Drama, Mystery',
                                          'hook': 'Захватывающий триллер с временной петлёй и смертоносными тенями на '
                                                  'острове.',
                                          'id': 47194,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx129201-HJBauga2be8I.png',
                                          'ru': 'Летнее время',
                                          'score': '8.47'},
                                      {   'en': 'Tengoku Daimakyo',
                                          'genres': 'Adventure, Mystery, Sci-Fi',
                                          'hook': 'Две параллельные тайны: закрытый райский приют и разрушенный '
                                                  'внешний мир.',
                                          'id': 53393,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx155783-YosKbsmZzuDE.jpg',
                                          'ru': 'Иллюзия рая',
                                          'score': '8.2'},
                                      {   'en': 'Boogiepop Phantom',
                                          'genres': 'Drama, Horror, Mystery',
                                          'hook': 'Мистическая сущность защищает мир от порождений человеческого '
                                                  'безумия.',
                                          'id': 369,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx369-dwzXLDvzzAmK.png',
                                          'ru': 'Бугипоп никогда не смеётся',
                                          'score': '7.17'},
                                      {   'en': 'When They Cry',
                                          'genres': 'Horror, Mystery, Psychological',
                                          'hook': 'Идиллическая деревня погружается в кровавые циклы безумия и '
                                                  'паранойи.',
                                          'id': 934,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx934-wjMlVEl4CWwg.jpg',
                                          'ru': 'Когда плачут цикады',
                                          'score': '7.87'},
                                      {   'en': 'Shiki',
                                          'genres': 'Horror, Mystery, Supernatural',
                                          'hook': 'Жуткая деконструкция вампиризма и морали выживания посреди '
                                                  'эпидемии.',
                                          'id': 7724,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7724-NwNnRsI34eDa.jpg',
                                          'ru': 'Усопшие',
                                          'score': '7.72'},
                                      {   'en': 'Link Click',
                                          'genres': 'Drama, Mystery, Supernatural',
                                          'hook': 'Два парня погружаются в фотографии ради чужих тайн, рискуя изменить '
                                                  'прошлое.',
                                          'id': 44074,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx126403-BfVSRzWUtVFW.png',
                                          'ru': 'Агент времени',
                                          'score': '8.7'},
                                      {   'en': 'Kaiji - Against All Rules',
                                          'genres': 'Psychological, Thriller',
                                          'hook': 'Напряжённейшая психологическая битва за жизнь и огромные деньги на '
                                                  'дне отчаяния.',
                                          'id': 10271,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx10271-Aep4woDDbXdU.jpg',
                                          'ru': 'Кайдзи 2',
                                          'score': '8.24'},
                                      {   'en': 'Kakegurui',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Элитная академия, где социальный статус решает мастерство азартных '
                                                  'игр.',
                                          'id': 34933,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b98314-TSJykxVwCCQN.jpg',
                                          'ru': 'Безумный азарт',
                                          'score': '7.21'},
                                      {   'en': 'Happy Sugar Life',
                                          'genres': 'Drama, Horror, Mystery',
                                          'hook': 'Обманчиво розовая, но пугающе безумная психологическая драма об '
                                                  'одержимости.',
                                          'id': 37517,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101351-TWLbnRdE1tBI.jpg',
                                          'ru': 'Сладкая жизнь',
                                          'score': '6.75'},
                                      {   'en': 'The Perfect Insider',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Классический интеллектуальный детектив об убийстве в неприступной '
                                                  'лаборатории.',
                                          'id': 28621,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21190-CcEb1nZfY729.jpg',
                                          'ru': 'Всё становится F: Идеальный инсайдер',
                                          'score': '7.23'},
                                      {   'en': 'BABYLON',
                                          'genres': 'Drama, Mystery, Psychological',
                                          'hook': 'Прокурор расследует суицидальный заговор и сталкивается с '
                                                  'воплощением чистого зла.',
                                          'id': 37525,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101349-AWy5SjUS8mYZ.jpg',
                                          'ru': 'Вавилон',
                                          'score': '6.73'},
                                      {   'en': 'Ergo Proxy',
                                          'genres': 'Adventure, Mystery, Psychological',
                                          'hook': 'Философский киберпанк-детектив о природе души искусственного '
                                                  'интеллекта.',
                                          'id': 790,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx790-YTUCvBKX8ZWK.jpg',
                                          'ru': 'Эрго Прокси',
                                          'score': '7.9'},
                                      {   'en': 'Devilman Crybaby',
                                          'genres': 'Хоррор, Триллер',
                                          'hook': 'Чистосердечный парень сливается с демоном, пытаясь спасти мир от '
                                                  'апокалипсиса.',
                                          'id': 35120,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98460-bLtH2c3jd6sV.png',
                                          'ru': 'Человек-дьявол: Плакса',
                                          'score': '7.60'},
                                      {   'en': 'One Outs',
                                          'genres': 'Спорт, Психология',
                                          'hook': 'Гениальный игрок-манипулятор превращает бейсбол в психологическую '
                                                  'войну умов.',
                                          'id': 5040,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5040-9ruuekq2LZKJ.png',
                                          'ru': 'Один на вылет',
                                          'score': '8.10'},
                                      {   'en': 'Akagi',
                                          'genres': 'Психология, Триллер',
                                          'hook': 'Хладнокровный юный гений маджонга бросает вызов криминальным '
                                                  'авторитетам Якудзы.',
                                          'id': 658,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx658-vfMTeXswhOzl.png',
                                          'ru': 'Акаги',
                                          'score': '7.70'},
                                      {   'en': 'Gakkougurashi!',
                                          'genres': 'Хоррор, Психология',
                                          'hook': 'Милая школьная жизнь клуба оказывается отчаянной иллюзией посреди '
                                                  'зомби-апокалипсиса.',
                                          'id': 26599,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                          'ru': 'Школьная жизнь!',
                                          'score': '7.65'},
                                      {   'en': 'Danganronpa: The Animation',
                                          'genres': 'Детектив, Триллер',
                                          'hook': 'Элитные школьники заперты медведем Монокумой и вынуждены судить '
                                                  'друг друга за убийства.',
                                          'id': 16592,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16592-mFn1gfMXlKtw.jpg',
                                          'ru': 'Данганронпа',
                                          'score': '6.90'},
                                      {   'en': 'Kubikiri Cycle: The Blue Savant and the Nonsense User',
                                          'genres': 'Детектив, Психология',
                                          'hook': 'На изолированном острове гениев происходит серия загадочных '
                                                  'обезглавливаний.',
                                          'id': 33263,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b21803-BAQClgq6Q0DP.jpg',
                                          'ru': 'Обезглавливающий цикл',
                                          'score': '7.70'},
                                      {   'en': 'In/Spectre',
                                          'genres': 'Детектив, Мистика',
                                          'hook': 'Богиня мудрости духов и бессмертный парень сочиняют правдоподобную '
                                                  'ложь ради порядка.',
                                          'id': 39017,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx107201-zQYOPotwmSXO.png',
                                          'ru': 'Ложные выводы',
                                          'score': '6.80'},
                                      {   'en': 'B: The Beginning',
                                          'genres': 'Детектив, Экшен',
                                          'hook': 'Гениальный следователь Кит Флик расследует ритуальные убийства '
                                                  'неуловимого Карателя «Би».',
                                          'id': 32827,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx21665-QnenQOaxzhpf.jpg',
                                          'ru': 'Би: Начало',
                                          'score': '6.90'},
                                      {   'en': 'Texhnolyze',
                                          'genres': 'Киберпанк, Трагедия',
                                          'hook': 'Мрачное падение человечества в подземном городе Люкс сквозь судьбу '
                                                  'бойца с протезами.',
                                          'id': 26,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx26-ADSztyHBNO39.jpg',
                                          'ru': 'Технолайз',
                                          'score': '7.60'},
                                      {   'en': 'Gosick',
                                          'genres': 'Детектив, Исторический',
                                          'hook': 'Кукольная гениальная Викторика щелкает неразрешимые тайны Европы в '
                                                  'библиотечной башне.',
                                          'id': 8425,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx8425-Bn14ayPjnq9o.jpg',
                                          'ru': 'Госик',
                                          'score': '7.70'},
                                      {   'en': 'Moriarty the Patriot',
                                          'genres': 'Детектив, Триллер',
                                          'hook': 'Уильям Джеймс Мориарти очищает викторианский Лондон от прогнившей '
                                                  'аристократии.',
                                          'id': 93692,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                          'ru': 'Патриотизм Мориарти',
                                          'score': '8.15'},
                                      {   'en': 'Zetsuen no Tempest',
                                          'genres': 'Мистика, Детектив',
                                          'hook': 'Два друга заключают союз с заточенной сильнейшей волшебницей ради '
                                                  'мести за сестру.',
                                          'id': 63369,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                          'ru': 'Буря потерь',
                                          'score': '7.90'},
                                      {   'en': 'Rampo Kitan: Game of Laplace',
                                          'genres': 'Детектив, Психология',
                                          'hook': 'Юный гений Кобаяси берется за расследование гротескных '
                                                  'преступлений.',
                                          'id': 28619,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21189-ENdHxDI7278o.jpg',
                                          'ru': 'Загадочные истории Ранпо',
                                          'score': '6.10'},
                                      {   'en': "Heaven's Memo Pad",
                                          'genres': 'Детектив, Драма',
                                          'hook': 'Хикикомори-детектив Алиса раскрывает преступления подпольного мира '
                                                  'с экрана монитора.',
                                          'id': 10568,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10568-QZbLhgMAQC76.jpg',
                                          'ru': 'Записная книжка бога',
                                          'score': '7.10'},
                                      {   'en': 'Black Butler: Book of Circus',
                                          'genres': 'Мистика, Детектив',
                                          'hook': 'Сиэль и Себастьян проникают в бродячий цирк «Ноев ковчег» в поисках '
                                                  'пропавших детей.',
                                          'id': 22145,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx20606-58LzabjtVrwt.jpg',
                                          'ru': 'Тёмный дворецкий: Книга цирка',
                                          'score': '7.90'},
                                      {   'en': 'Pretty Boy Detective Club',
                                          'genres': 'Детектив, Эстетика',
                                          'hook': 'Пятеро одаренных эксцентричных юношей расследуют эстетичные тайны '
                                                  'академии.',
                                          'id': 40752,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113428-jsyIdAHk5K6q.png',
                                          'ru': 'Красавчики-детективы',
                                          'score': '6.90'},
                                      {   'en': 'Psychic Detective Yakumo',
                                          'genres': 'Мистика, Детектив',
                                          'hook': 'Студент с алым левым глазом видит призраков и раскрывает '
                                                  'нераскрытые преступления.',
                                          'id': 7662,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7662-uW1oWpFeENgf.png',
                                          'ru': 'Детектив-медиум Якумо',
                                          'score': '6.80'},
                                      {   'en': 'UN-GO',
                                          'genres': 'Детектив, Sci-Fi',
                                          'hook': '«Пораженческий детектив» Синдзюро Юки и загадочный демон Инга '
                                                  'расследуют заговоры послевоенного Токио.',
                                          'id': 10798,
                                          'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10798-C8caHKEm5uTa.jpg',
                                          'ru': 'Ан-го',
                                          'score': '7.00'}],
                    'desc': 'Напряженные сюжеты, заговоры и неожиданные сюжетные твисты:',
                    'key': 'mindfuck',
                    'name': '🧠 Игры разума, психологические триллеры и детективы',
                    'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1535-kUgkcrfOrkUM.jpg',
                    'shiki_genre': None,
                    'shiki_order': None,
                    'tags': '#триллер #психология #игрыразума',
                    'title': 'Игры разума и психологические триллеры 🧠'},
    'must_watch': {   'candidates': [   {   'en': 'Sousou no Frieren',
                                            'genres': 'Фэнтези, Драма',
                                            'hook': 'Бессмертная эльфийка отправляется в путь, чтобы постичь ценность '
                                                    'человеческой жизни.',
                                            'id': 52991,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                            'ru': 'Провожающая в последний путь Фрирен',
                                            'score': '9.10'},
                                        {   'en': 'Hagane no Renkinjutsushi: FULLMETAL ALCHEMIST',
                                            'genres': 'Сёнэн, Фэнтези',
                                            'hook': 'Братья Элрики ищут философский камень, чтобы вернуть утраченные '
                                                    'тела.',
                                            'id': 5114,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5114-nSWCgQlmOMtj.jpg',
                                            'ru': 'Стальной алхимик: Братство',
                                            'score': '9.00'},
                                        {   'en': 'Steins;Gate',
                                            'genres': 'Фантастика, Триллер',
                                            'hook': 'Случайное создание машины времени втягивает друзей в опаснейший '
                                                    'заговор.',
                                            'id': 9253,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx9253-tIUXF2gfU8Sg.jpg',
                                            'ru': 'Врата Штейна',
                                            'score': '8.90'},
                                        {   'en': 'HUNTER×HUNTER (2011)',
                                            'genres': 'Экшен, Приключения',
                                            'hook': 'Гон отправляется на смертельный экзамен Охотников ради поисков '
                                                    'отца.',
                                            'id': 11061,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11061-y5gsT1hoHuHw.png',
                                            'ru': 'Охотник х Охотник',
                                            'score': '8.90'},
                                        {   'en': 'Monster',
                                            'genres': 'Драма, Триллер',
                                            'hook': 'Гениальный хирург спасает жизнь мальчику, не зная, что взрастил '
                                                    'зло.',
                                            'id': 61629,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx19-gtMC64182sm4.jpg',
                                            'ru': 'Монстр',
                                            'score': '8.80'},
                                        {   'en': 'Cowboy Bebop',
                                            'genres': 'Фантастика, Экшен',
                                            'hook': 'Охотники за головами бороздят Солнечную систему под звуки джаза.',
                                            'id': 1,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1-GCsPm7waJ4kS.png',
                                            'ru': 'Ковбой Бибоп',
                                            'score': '8.60'},
                                        {   'en': 'Tengen Toppa Gurren Lagann',
                                            'genres': 'Экшен, Меха',
                                            'hook': 'Симон и Камина бурят путь наверх сквозь пространство, бросая '
                                                    'вызов Вселенной.',
                                            'id': 2001,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2001-XwRnjzGeFWRQ.png',
                                            'ru': 'Гуррен-Лаганн',
                                            'score': '8.50'},
                                        {   'en': 'Code Geass: Hangyaku no Lelouch',
                                            'genres': 'Экшен, Меха',
                                            'hook': 'Отвергнутый принц получает силу абсолютного подчинения и начинает '
                                                    'восстание.',
                                            'id': 1575,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1575-hsmWM2ydNm1m.jpg',
                                            'ru': 'Код Гиас: Восставший Лелуш',
                                            'score': '8.50'},
                                        {   'en': 'DEATH NOTE',
                                            'genres': 'Мистика, Детектив',
                                            'hook': 'Интеллектуальная дуэль школьника с тетрадью бога смерти и '
                                                    'гениального сыщика L.',
                                            'id': 1535,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1535-kUgkcrfOrkUM.jpg',
                                            'ru': 'Тетрадь смерти',
                                            'score': '8.40'},
                                        {   'en': 'GTO',
                                            'genres': 'Комедия, Школа',
                                            'hook': 'Бывший байкер берется перевоспитывать самый проблемный класс '
                                                    'школы.',
                                            'id': 245,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx245-NcQAyTipUMeO.jpg',
                                            'ru': 'Крутой учитель Онидзука',
                                            'score': '8.40'},
                                        {   'en': 'Samurai Champloo',
                                            'genres': 'Экшен, Приключения',
                                            'hook': 'Два непревзойденных мечника сопровождают девушку в поисках '
                                                    'самурая.',
                                            'id': 205,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx205-7tHVFu6dPBm9.png',
                                            'ru': 'Самурай Чамплу',
                                            'score': '8.40'},
                                        {   'en': 'Shin Seiki Evangelion',
                                            'genres': 'Меха, Психология',
                                            'hook': 'Подростки пилотируют биороботов, защищая мир от таинственных '
                                                    'Ангелов.',
                                            'id': 30,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx30-AI1zr74Dh4ye.jpg',
                                            'ru': 'Евангелион',
                                            'score': '8.30'},
                                        {   'en': 'Sen to Chihiro no Kamikakushi',
                                            'genres': 'Сказка, Мистика',
                                            'hook': 'Десятилетняя Тихиро попадает в таинственный мир духов и ведьмы '
                                                    'Юбабы.',
                                            'id': 199,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx199-sWefXJvXkDOb.jpg',
                                            'ru': 'Унесённые призраками',
                                            'score': '8.60'},
                                        {   'en': 'Shingeki no Kyojin',
                                            'genres': 'Экшен, Драма',
                                            'hook': 'Остатки человечества сражаются за выживание с '
                                                    'гигантами-людоедами.',
                                            'id': 16498,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16498-buvcRTBx4NSm.jpg',
                                            'ru': 'Атака титанов',
                                            'score': '8.50'},
                                        {   'en': 'Vinland Saga',
                                            'genres': 'Action, Adventure, Drama',
                                            'hook': 'Суровый исторический эпос о мести, викингах и поиске истинного '
                                                    'пути.',
                                            'id': 37521,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101348-2fhDFPCuMNiz.jpg',
                                            'ru': 'Сага о Винланде',
                                            'score': '8.78'},
                                        {   'en': 'Clannad: After Story',
                                            'genres': 'Drama, Romance, Slice of Life',
                                            'hook': 'Трогательная до слёз история взросления, семьи и настоящей любви.',
                                            'id': 4181,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx4181-zUKE7BZC62OF.png',
                                            'ru': 'Кланнад: Продолжение истории',
                                            'score': '8.93'},
                                        {   'en': 'HAIKYU!!',
                                            'genres': 'Comedy, Drama, Sports',
                                            'hook': 'Невероятно вдохновляющая спортивная драма о преодолении и '
                                                    'командном духе.',
                                            'id': 20583,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20464-ooZUyBe4ptp9.png',
                                            'ru': 'Волейбол!!',
                                            'score': '8.43'},
                                        {   'en': 'Mob Psycho 100',
                                            'genres': 'Action, Comedy, Drama',
                                            'hook': 'Школьник с богоподобной силой учится быть человеком и ценить '
                                                    'доброту.',
                                            'id': 32182,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21507-6YUSbh2m0N1p.jpg',
                                            'ru': 'Моб Психо 100',
                                            'score': '8.49'},
                                        {   'en': 'Made in Abyss',
                                            'genres': 'Adventure, Drama, Fantasy',
                                            'hook': 'Обманчиво милое, но пугающе глубокое путешествие на дно '
                                                    'неизведанного мира.',
                                            'id': 34599,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97986-TQ7dCgbS3y5s.jpg',
                                            'ru': 'Созданный в Бездне',
                                            'score': '8.62'},
                                        {   'en': 'Violet Evergarden',
                                            'genres': 'Drama, Fantasy, Slice of Life',
                                            'hook': 'Бывшее живое оружие учится понимать человеческие чувства, сочиняя '
                                                    'письма.',
                                            'id': 33352,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21827-ubzq619ZA2E9.png',
                                            'ru': 'Вайолет Эвергарден',
                                            'score': '8.69'},
                                        {   'en': 'Your Name.',
                                            'genres': 'Drama, Romance, Supernatural',
                                            'hook': 'Романтическая фантастика Макото Синкая о связи душ сквозь время и '
                                                    'расстояние.',
                                            'id': 32281,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21519-SUo3ZQuCbYhJ.png',
                                            'ru': 'Твоё имя',
                                            'score': '8.82'},
                                        {   'en': 'Princess Mononoke',
                                            'genres': 'Action, Adventure, Drama',
                                            'hook': 'Шедевр Хаяо Миядзаки о великом противостоянии природы и '
                                                    'цивилизации.',
                                            'id': 164,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx164-ySuGzCWVw2cL.jpg',
                                            'ru': 'Принцесса Мононоке',
                                            'score': '8.67'},
                                        {   'en': 'Ping Pong the Animation',
                                            'genres': 'Drama, Psychological, Sports',
                                            'hook': 'Авангардный шедевр Масааки Юасы о дружбе, спорте и поиске себя.',
                                            'id': 22135,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20607-fIOxVISIl0HY.jpg',
                                            'ru': 'Пинг-понг',
                                            'score': '8.63'},
                                        {   'en': 'From the New World',
                                            'genres': 'Drama, Horror, Mystery',
                                            'hook': 'Глубокая психологическая антиутопия в мире победившего '
                                                    'телекинеза.',
                                            'id': 13125,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx13125-2EDZb8ahshQc.png',
                                            'ru': 'Из нового света',
                                            'score': '8.24'},
                                        {   'en': 'Fate/Zero',
                                            'genres': 'Action, Drama, Fantasy',
                                            'hook': 'Бескомпромиссная война магов и героических душ за исполнение '
                                                    'любого желания.',
                                            'id': 10087,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10087-M4Hd9qrHGrXk.png',
                                            'ru': 'Судьба/Начало',
                                            'score': '8.26'},
                                        {   'en': 'Chainsaw Man',
                                            'genres': 'Action, Drama, Horror',
                                            'hook': 'Ураганный безумный экшен о демонах, долгах и простых человеческих '
                                                    'мечтах.',
                                            'id': 44511,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx127230-DdP4vAdssLoz.png',
                                            'ru': 'Человек-бензопила',
                                            'score': '8.42'},
                                        {   'en': 'JUJUTSU KAISEN',
                                            'genres': 'Action, Drama, Supernatural',
                                            'hook': 'Динамичная сага о борьбе с опасными проклятиями и цене силы.',
                                            'id': 40748,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113415-LHBAeoZDIsnF.jpg',
                                            'ru': 'Магическая битва',
                                            'score': '8.5'},
                                        {   'en': 'ODDTAXI',
                                            'genres': 'Drama, Mystery, Psychological',
                                            'hook': 'Гениальный неонуарный детектив с антропоморфными зверями и '
                                                    'твистами.',
                                            'id': 46102,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx128547-nNekWTKqmvEi.jpg',
                                            'ru': 'Случайное такси',
                                            'score': '8.62'},
                                        {   'en': 'Sonny Boy',
                                            'genres': 'Drama, Mystery, Psychological',
                                            'hook': 'Сюрреалистичный артхаус о дрейфе школьного класса между '
                                                    'параллельными мирами.',
                                            'id': 48849,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx132126-4ugVjXMQLAps.png',
                                            'ru': 'Сонни Бой',
                                            'score': '7.86'},
                                        {   'en': 'Golden Kamuy',
                                            'genres': 'Action, Adventure, Comedy',
                                            'hook': 'Колоритная охота за золотом айнов на суровых просторах Хоккайдо.',
                                            'id': 36028,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99699-mBCjpoWpAVGX.jpg',
                                            'ru': 'Золотое божество',
                                            'score': '7.89'},
                                        {   'en': 'Hellsing Ultimate',
                                            'genres': 'Action, Horror, Supernatural',
                                            'hook': 'Культовое кровавое противостояние вампира Алукарда и '
                                                    'нацистов-оккультистов.',
                                            'id': 777,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx777-F6547pSAR2Zd.jpg',
                                            'ru': 'Хеллсинг OVA',
                                            'score': '8.34'},
                                        {   'en': 'Black Lagoon',
                                            'genres': 'Action, Adventure, Drama',
                                            'hook': 'Адреналиновый боевик о наёмниках в криминальной столице Таиланда.',
                                            'id': 889,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx889-4S7N2ciq2cwA.png',
                                            'ru': 'Пираты «Чёрной лагуны»',
                                            'score': '8.04'},
                                        {   'en': 'NANA',
                                            'genres': 'Drama, Music, Romance',
                                            'hook': 'Взрослая и искренняя драма о двух совершенно разных девушках с '
                                                    'одинаковым именем.',
                                            'id': 877,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx877-6BUYEWp8By8j.png',
                                            'ru': 'Нана',
                                            'score': '8.57'},
                                        {   'en': 'A Silent Voice',
                                            'genres': 'Drama, Romance, Slice of Life',
                                            'hook': 'Проникновенная драма об искуплении вины перед глухой девочкой.',
                                            'id': 28851,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20954-sYRfE5jQRtSB.jpg',
                                            'ru': 'Форма голоса',
                                            'score': '8.93'},
                                        {   'en': 'Your lie in April',
                                            'genres': 'Drama, Music, Romance',
                                            'hook': 'Музыкальная история о любви, трагедии и возвращении вкуса к '
                                                    'жизни.',
                                            'id': 23273,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20665-TLgkL8T8IRFd.png',
                                            'ru': 'Твоя апрельская ложь',
                                            'score': '8.64'},
                                        {   'en': 'Cyberpunk: Edgerunners',
                                            'genres': 'Action, Drama, Psychological',
                                            'hook': 'Взрывная трагедия парня из трущоб в безжалостном Найт-Сити.',
                                            'id': 42310,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx120377-ayZPoxiWt4Li.jpg',
                                            'ru': 'Киберпанк: Бегущие по краю',
                                            'score': '8.62'},
                                        {   'en': 'PLUTO',
                                            'genres': 'Sci-Fi, Детектив',
                                            'hook': 'Робот-детектив расследует серию загадочных убийств сильнейших '
                                                    'роботов планеты.',
                                            'id': 35737,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99088-LTJskMD1wbbQ.png',
                                            'ru': 'Плутон',
                                            'score': '8.40'},
                                        {   'en': 'Slam Dunk',
                                            'genres': 'Спорт, Комедия',
                                            'hook': 'Хулиган Сакураги приходит в баскетбол ради девушки и открывает в '
                                                    'себе невероятный талант.',
                                            'id': 170,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx170-cmD8A0vZsp6g.jpg',
                                            'ru': 'Слэм-данк',
                                            'score': '8.30'},
                                        {   'en': 'Hajime No Ippo: The Fighting! - Rising -',
                                            'genres': 'Спорт, Драма',
                                            'hook': 'Застенчивый школьник находит спасение в боксе и начинает путь к '
                                                    'поясу чемпиона.',
                                            'id': 19647,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx19647-cIy7ShTL6e9h.jpg',
                                            'ru': 'Первый шаг',
                                            'score': '8.50'},
                                        {   'en': 'Ghost in the Shell: Stand Alone Complex',
                                            'genres': 'Sci-Fi, Киберпанк',
                                            'hook': 'Майор Мотоко Кусанаги и 9-й отдел ведут борьбу с изощрённым '
                                                    'хакером Смеющимся человеком.',
                                            'id': 467,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx467-mBTtIoR13qs2.jpg',
                                            'ru': 'Призрак в доспехах: Синдром одиночки',
                                            'score': '8.20'},
                                        {   'en': 'Evangelion: 3.0+1.0 Thrice Upon a Time',
                                            'genres': 'Меха, Драма',
                                            'hook': 'Грандиозный и трогательный финал легендарной эпопеи Синдзи Икари.',
                                            'id': 3786,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx3786-Tpt9iM72dxTv.jpg',
                                            'ru': 'Евангелион 3.0+1.0',
                                            'score': '8.50'},
                                        {   'en': 'Suzume',
                                            'genres': 'Фэнтези, Приключения',
                                            'hook': 'Девушка и парень-хранитель путешествуют по Японии, закрывая двери '
                                                    'бедствий.',
                                            'id': 50594,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx142770-dDaDIRnsv5jN.jpg',
                                            'ru': 'Судзумэ, закрывающая двери',
                                            'score': '8.10'},
                                        {   'en': 'Weathering With You',
                                            'genres': 'Романтика, Фэнтези',
                                            'hook': 'Сбежавший в Токио подросток встречает девушку, способную '
                                                    'разгонять тучи силой молитвы.',
                                            'id': 38826,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx106286-5COcpd0J9VbL.png',
                                            'ru': 'Дитя погоды',
                                            'score': '8.10'},
                                        {   'en': 'I Want to Eat Your Pancreas',
                                            'genres': 'Драма, Романтика',
                                            'hook': 'Скрытный парень узнаёт о смертельной болезни одноклассницы и '
                                                    'проводит с ней последние дни.',
                                            'id': 36098,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99750-pNyly9d3MEgV.jpg',
                                            'ru': 'Я хочу съесть твою поджелудочную',
                                            'score': '8.40'},
                                        {   'en': 'Gintama',
                                            'genres': 'Комедия, Сёнэн',
                                            'hook': 'Безумная жизнь ленивого самурая Гинтоки в оккупированном '
                                                    'пришельцами Эдо.',
                                            'id': 918,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx918-iOaeBVUn4uK7.jpg',
                                            'ru': 'Гинтама',
                                            'score': '8.50'},
                                        {   'en': 'OSHI NO KO',
                                            'genres': 'Драма, Детектив',
                                            'hook': 'Обратная сторона японского шоу-бизнеса сквозь призму мести и '
                                                    'реинкарнации.',
                                            'id': 52034,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx150672-WqmmwZ4nMzAy.png',
                                            'ru': 'Звёздное дитя',
                                            'score': '8.40'},
                                        {   'en': 'Delicious in Dungeon',
                                            'genres': 'Фэнтези, Приключения',
                                            'hook': 'Отряд авантюристов спускается в смертоносное подземелье, готовя '
                                                    'монстров на обед.',
                                            'id': 52701,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx153518-IVXPDY5ph3kO.jpg',
                                            'ru': 'Подземелье вкусностей',
                                            'score': '8.50'},
                                        {   'en': "Cowboy Bebop: The Movie - Knockin' on Heaven's Door",
                                            'genres': 'Sci-Fi, Боевик',
                                            'hook': 'Спайк Шпигель и команда Бибопа охотятся за террористом с '
                                                    'биооружием на Марсе.',
                                            'id': 5,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5-NozHwXWdNLCz.jpg',
                                            'ru': 'Ковбой Бибоп: Достучаться до небес',
                                            'score': '8.20'},
                                        {   'en': 'TRIGUN STAMPEDE',
                                            'genres': 'Sci-Fi, Экшен',
                                            'hook': 'Пацифист Вэш Ураган путешествует по пустынной планете, спасая '
                                                    'людей от разрушений.',
                                            'id': 52093,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx151040-9QXRpaprfNmL.png',
                                            'ru': 'Триган: Ураган',
                                            'score': '7.70'},
                                        {   'en': 'Dororo',
                                            'genres': 'Экшен, Исторический',
                                            'hook': 'Юноша, лишённый тела из-за сделки отца с демонами, ищет чудовищ, '
                                                    'чтобы вернуть себя.',
                                            'id': 37520,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101347-TGaDwEYqLfm1.jpg',
                                            'ru': 'Дороро',
                                            'score': '8.10'},
                                        {   'en': 'Bungo Stray Dogs',
                                            'genres': 'Экшен, Детектив',
                                            'hook': 'Детективное агентство с литературными суперсилами противостоит '
                                                    'портовой мафии.',
                                            'id': 31478,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21311-hAXyT8Yoh6G9.jpg',
                                            'ru': 'Великий из бродячих псов',
                                            'score': '7.70'},
                                        {   'en': 'Chihayafuru',
                                            'genres': 'Драма, Спорт',
                                            'hook': 'Девушка стремится стать королевой традиционной японской карточной '
                                                    'игры Карута.',
                                            'id': 10800,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10800-hofcUL0YEL7O.png',
                                            'ru': 'Яркая Чихая',
                                            'score': '8.00'},
                                        {   'en': 'Hyouka',
                                            'genres': 'Детектив, Повседневность',
                                            'hook': 'Энергосберегающий парень Хотаро раскрывает школьные бытовые тайны '
                                                    'ради любопытной подруги.',
                                            'id': 12189,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx12189-zj5AWUYO53Fv.jpg',
                                            'ru': 'Хёка',
                                            'score': '7.90'},
                                        {   'en': 'Run with the Wind',
                                            'genres': 'Спорт, Драма',
                                            'hook': 'Десять студентов с нуля готовятся к сложнейшему марафонскому '
                                                    'забегу Хаконэ Экидэн.',
                                            'id': 37965,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101903-ncgPJbbA5Nou.jpg',
                                            'ru': 'Почувствуй ветер',
                                            'score': '8.30'},
                                        {   'en': "Kuroko's Basketball",
                                            'genres': 'Спорт, Сёнэн',
                                            'hook': '«Призрачный шестой игрок» Поколения Чудес ведет команду Сэйрин к '
                                                    'национальному триумфу.',
                                            'id': 11771,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11771-uvr44RAwRxPw.jpg',
                                            'ru': 'Баскетбол Куроко',
                                            'score': '7.80'},
                                        {   'en': 'Ghost in the Shell',
                                            'genres': 'Киберпанк, Философия',
                                            'hook': 'Культовый шедевр Мамору Осии о майоре Кусанаги и природе '
                                                    'искусственного разума.',
                                            'id': 43,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx43-Y6EjeEMM14dj.png',
                                            'ru': 'Призрак в доспехах (1995)',
                                            'score': '8.00'},
                                        {   'en': 'Akira',
                                            'genres': 'Sci-Fi, Киберпанк',
                                            'hook': 'Легендарный визуальный прорыв о Нео-Токио, байкерах и '
                                                    'высвобождении колоссальной телекинетической силы.',
                                            'id': 47,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx47-4CR68arv452h.jpg',
                                            'ru': 'Акира',
                                            'score': '7.90'},
                                        {   'en': 'Wolf Children',
                                            'genres': 'Драма, Фэнтези',
                                            'hook': 'Одинокая мать растит двоих детей-полуволков, ищущих свое место в '
                                                    'мире.',
                                            'id': 12355,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx12355-wNsvhEsXEgrH.png',
                                            'ru': 'Волчьи дети Амэ и Юки',
                                            'score': '8.30'},
                                        {   'en': 'The Boy and the Beast',
                                            'genres': 'Приключения, Фэнтези',
                                            'hook': 'Сбежавший мальчик попадает в мир духов и становится учеником '
                                                    'вспыльчивого воина-медведя.',
                                            'id': 28805,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20981-D6PAJAOC4jPc.jpg',
                                            'ru': 'Ученик чудовища',
                                            'score': '7.90'},
                                        {   'en': 'Mirai',
                                            'genres': 'Фэнтези, Семья',
                                            'hook': 'Мальчик Кун ревнует родителей к новорожденной сестренке и '
                                                    'встречает ее повзрослевшую версию из будущего.',
                                            'id': 36936,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx100749-7Tptl7EAMAWH.jpg',
                                            'ru': 'Мирай из будущего',
                                            'score': '7.10'},
                                        {   'en': 'Ride Your Wave',
                                            'genres': 'Романтика, Драма',
                                            'hook': 'Девушка-серфингистка видит дух погибшего возлюбленного-пожарного '
                                                    'в воде при пении их любимой песни.',
                                            'id': 38594,
                                            'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105018-XM7rFyryltjb.jpg',
                                            'ru': 'На твоей волне',
                                            'score': '7.60'}],
                      'desc': 'Культовые тайтлы с высочайшим мировым рейтингом, навсегда вошедшие в историю:',
                      'key': 'must_watch',
                      'name': '🏆 Золотая классика и шедевры (8.5+)',
                      'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                      'shiki_genre': None,
                      'shiki_order': None,
                      'tags': '#шедевры #must_watch #топ_аниме',
                      'title': 'Золотая классика и шедевры (8.5+) 🏆'},
    'pure_comedy': {   'candidates': [   {   'en': 'Gintama',
                                             'genres': 'Пародия, Экшен',
                                             'hook': 'Самураи, пришельцы и мастер абсурдного юмора Гинтоки Саката в '
                                                     'феодальной Японии.',
                                             'id': 918,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx918-iOaeBVUn4uK7.jpg',
                                             'ru': 'Гинтама',
                                             'score': '8.50'},
                                         {   'en': 'Grand Blue',
                                             'genres': 'Комедия, Студенты',
                                             'hook': 'Безумная жизнь студенческого дайвинг-клуба, полная угарных '
                                                     'вечеринок и дружбы.',
                                             'id': 37105,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx100922-uxEhaCsqMMp3.png',
                                             'ru': 'Необъятный океан',
                                             'score': '8.20'},
                                         {   'en': 'Saiki Kusuo no Ψ-nan',
                                             'genres': 'Комедия, Сверхъестественное',
                                             'hook': 'Могущественный экстрасенс хочет спокойной жизни, но чудаки '
                                                     'вокруг не дают покоя.',
                                             'id': 33255,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21804-As6tDLAvEvNY.jpg',
                                             'ru': 'Несладкая жизнь псионика Сайки К.',
                                             'score': '8.30'},
                                         {   'en': 'Kono Subarashii Sekai ni Shukufuku wo!',
                                             'genres': 'Комедия, Пародия',
                                             'hook': 'Казума берет с собой бесполезную богиню Акву и собирает '
                                                     'чудаковатую команду.',
                                             'id': 30831,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21202-mPOr80AEjUcZ.png',
                                             'ru': 'Этот замечательный мир! (KonoSuba)',
                                             'score': '7.90'},
                                         {   'en': 'Mob Psycho 100',
                                             'genres': 'Экшен, Комедия',
                                             'hook': 'Школьник с колоссальной телекинетической силой пытается жить '
                                                     'обычной жизнью.',
                                             'id': 32182,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21507-6YUSbh2m0N1p.jpg',
                                             'ru': 'Моб Психо 100',
                                             'score': '8.40'},
                                         {   'en': 'GTO',
                                             'genres': 'Комедия, Школа',
                                             'hook': 'Бывший главарь банды байкеров учит трудных подростков настоящей '
                                                     'жизни.',
                                             'id': 245,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx245-NcQAyTipUMeO.jpg',
                                             'ru': 'Крутой учитель Онидзука',
                                             'score': '8.40'},
                                         {   'en': 'Danshi Koukousei no Nichijou',
                                             'genres': 'Комедия, Повседневность',
                                             'hook': 'Реалистичный и уморительный взгляд на будни трех школьных '
                                                     'оболтусов.',
                                             'id': 11843,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11843-ui2jBcuQUqnl.jpg',
                                             'ru': 'Повседневная жизнь старшеклассников',
                                             'score': '8.00'},
                                         {   'en': 'Hataraku Maou-sama!',
                                             'genres': 'Комедия, Фэнтези',
                                             'hook': 'Владыка тьмы попадает в современный Токио и устраивается жарить '
                                                     'бургеры.',
                                             'id': 15809,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx15809-ECv3HyOYJKrk.jpg',
                                             'ru': 'Сатана на подработке!',
                                             'score': '7.50'},
                                         {   'en': 'Kage no Jitsuryokusha ni Naritakute!',
                                             'genres': 'Экшен, Пародия',
                                             'hook': 'Парень играет роль серого кардинала, не зная, что все его '
                                                     'выдумки реальны.',
                                             'id': 48316,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx130298-YMdcKHytpWNH.jpg',
                                             'ru': 'Восхождение в тени!',
                                             'score': '8.10'},
                                         {   'en': 'SPY×FAMILY',
                                             'genres': 'Комедия, Экшен',
                                             'hook': 'Шпион, наемная убийца и девочка-телепат создают фиктивную '
                                                     'образцовую семью.',
                                             'id': 50265,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx140960-Kb6R5nYQfjmP.jpg',
                                             'ru': 'Семья шпиона',
                                             'score': '8.30'},
                                         {   'en': 'SK∞',
                                             'genres': 'Спорт, Комедия',
                                             'hook': 'Драйвовые нелегальные гонки на скейтах по заброшенной шахте на '
                                                     'Окинаве.',
                                             'id': 42923,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx124153-uEBI764OSavB.png',
                                             'ru': 'Скейт: Бесконечность',
                                             'score': '8.00'},
                                         {   'en': 'Baka to Test to Shoukanjuu',
                                             'genres': 'Комедия, Романтика',
                                             'hook': 'Битва школьных классов за комфорт в кабинетах с помощью '
                                                     'призванных аватаров.',
                                             'id': 6347,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6347-DCSHLkCY7UT3.jpg',
                                             'ru': 'Дурни, тесты и призванные существа',
                                             'score': '7.10'},
                                         {   'en': 'Nichijou - My Ordinary Life',
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Абсурдный комедийный шедевр студии KyoAni о буднях самых '
                                                     'невероятных школьниц.',
                                             'id': 10165,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx10165-tw8Cz7K9tfVJ.png',
                                             'ru': 'Мелочи жизни',
                                             'score': '8.47'},
                                         {   'en': 'Asobi Asobase - workshop of fun -',
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Ангельские с виду школьницы устраивают безумнейшие и упоротые '
                                                     'розыгрыши.',
                                             'id': 37171,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101001-UERCW0UGi0P7.jpg',
                                             'ru': 'Давайте сыграем',
                                             'score': '8.19'},
                                         {   'en': 'HINAMATSURI',
                                             'genres': 'Comedy, Sci-Fi, Slice of Life',
                                             'hook': 'Молодой якудза вынужден воспитывать девочку с телекинезом из '
                                                     'другого измерения.',
                                             'id': 36296,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx100077-FgGYIt8gGyrn.jpg',
                                             'ru': 'Праздник кукол',
                                             'score': '8.11'},
                                         {   'en': 'Barakamon',
                                             'genres': 'Slice of Life',
                                             'hook': 'Вспыльчивый каллиграф отправляется в глухую деревню ради '
                                                     'вдохновения и покоя.',
                                             'id': 22789,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20722-2KAeq72E95dr.png',
                                             'ru': 'Баракамон',
                                             'score': '8.36'},
                                         {   'en': 'Prison School',
                                             'genres': 'Comedy, Ecchi',
                                             'hook': 'Пятеро парней в женской академии попадают в карцер под надзор '
                                                     'строгого студсовета.',
                                             'id': 30240,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20807-8nFoO0AUdGsy.jpg',
                                             'ru': 'Школа-тюрьма',
                                             'score': '7.58'},
                                         {   'en': "Monthly Girls' Nozaki-kun",
                                             'genres': 'Comedy, Romance, Slice of Life',
                                             'hook': 'Школьница признается в любви парню, но случайно становится его '
                                                     'ассистенткой мангаки.',
                                             'id': 23289,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20668-6UslJY5NDYNh.png',
                                             'ru': 'Ежемесячное сёдзё Нодзаки',
                                             'score': '7.81'},
                                         {   'en': "Haven't You Heard? I'm Sakamoto",
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Идеальный во всём старшеклассник выходит победителем из любой '
                                                     'нелепой ситуации.',
                                             'id': 32542,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21595-vQ658r2Roe1g.jpg',
                                             'ru': 'Я — Сакамото, а что?',
                                             'score': '7.53'},
                                         {   'en': 'MASHLE: MAGIC AND MUSCLES',
                                             'genres': 'Action, Comedy, Fantasy',
                                             'hook': 'Парень без магии поступает в магическую академию, решая всё '
                                                     'чистой физической силой.',
                                             'id': 52211,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx151801-XxVf22Le6C8o.png',
                                             'ru': 'Магия и мускулы',
                                             'score': '7.61'},
                                         {   'en': 'Seitokai Yakuindomo',
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Парень попадает в женский студсовет, где все разговоры '
                                                     'скатываются в пошлые шутки.',
                                             'id': 8675,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx8675-5H2QSLvXA7bH.jpg',
                                             'ru': 'Члены школьного совета',
                                             'score': '7.54'},
                                         {   'en': 'Cromartie High School',
                                             'genres': 'Comedy',
                                             'hook': 'Единственный нормальный ученик в школе, где учатся гориллы, '
                                                     'бандиты и Фредди Меркьюри.',
                                             'id': 114,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx114-VqL7lYKqdBR6.png',
                                             'ru': 'Кромешная путяга',
                                             'score': '7.89'},
                                         {   'en': 'GOLDEN BOY',
                                             'genres': 'Adventure, Comedy, Ecchi',
                                             'hook': 'Кинтаро Оэ странствует по Японии на велосипеде, изучая жизнь и '
                                                     'попадая в передряги.',
                                             'id': 268,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx268-0T6bdW9CzVvz.png',
                                             'ru': 'Золотой парень',
                                             'score': '8.04'},
                                         {   'en': 'Detroit Metal City',
                                             'genres': 'Comedy, Music',
                                             'hook': 'Скромный фанат поп-музыки поневоле становится лидером '
                                                     'сатанинской метал-группы.',
                                             'id': 3702,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx3702-TCo0UYxWQzYj.jpg',
                                             'ru': 'Детройт, город металла',
                                             'score': '8.09'},
                                         {   'en': 'Tanaka-kun is Always Listless',
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Уморительно ленивый школьник превращает искусство безделья в '
                                                     'философию жизни.',
                                             'id': 32093,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21495-I6p0OKzKBFjw.png',
                                             'ru': 'Всегда вялый Танака-кун',
                                             'score': '7.79'},
                                         {   'en': 'Sleepy Princess in the Demon Castle',
                                             'genres': 'Comedy, Fantasy, Slice of Life',
                                             'hook': 'Похищенная принцесса кошмарит Владыку демонов ради идеального '
                                                     'сна.',
                                             'id': 40397,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx111428-JGrnjBDHLGQb.png',
                                             'ru': 'Сон в замке демона',
                                             'score': '7.95'},
                                         {   'en': 'Wasteful Days of High School Girls',
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Безумные и бессмысленные разговоры трёх подруг о парнях и жизни.',
                                             'id': 38619,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105081-pc4jgCmAP0dZ.jpg',
                                             'ru': 'Бездельные дни старшеклассницы',
                                             'score': '7.71'},
                                         {   'en': "Chio's School Road",
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Обычный путь в школу превращается в полосу препятствий на грани '
                                                     'экшена.',
                                             'id': 35821,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99366-niYV5CEsEhnc.jpg',
                                             'ru': 'Дорога в школу Чио',
                                             'score': '7.46'},
                                         {   'en': 'D-Frag!',
                                             'genres': 'Comedy',
                                             'hook': 'Школьный хулиган против воли вступает в безумный клуб создания '
                                                     'игр.',
                                             'id': 20031,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20031-WOR6bly9HOr1.jpg',
                                             'ru': 'Дефрагментация!',
                                             'score': '7.49'},
                                         {   'en': 'Arakawa Under the Bridge',
                                             'genres': 'Comedy, Romance',
                                             'hook': 'Успешный наследник корпорации селится под мостом среди '
                                                     'эксцентричных чудаков.',
                                             'id': 7647,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7647-NQEKHruZT5ch.jpg',
                                             'ru': 'Под мостом над Аракавой',
                                             'score': '7.56'},
                                         {   'en': 'Blood Lad',
                                             'genres': 'Action, Adventure, Comedy',
                                             'hook': 'Вампир-отаку пытается воскресить девушку, случайно ставшую '
                                                     'призраком в аду.',
                                             'id': 11633,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11633-vIjtabJq64Xt.jpg',
                                             'ru': 'Кровавый парень',
                                             'score': '7.23'},
                                         {   'en': 'Wagnaria!!',
                                             'genres': 'Comedy, Slice of Life',
                                             'hook': 'Веселые будни и романтические недопонимания персонала семейного '
                                                     'ресторана.',
                                             'id': 6956,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6956-Nxs7H25yHLNS.jpg',
                                             'ru': 'Работа!!',
                                             'score': '7.64'},
                                         {   'en': 'The Way of the Househusband',
                                             'genres': 'Комедия, Повседневность',
                                             'hook': 'Легендарный бессмертный якудза завязывает с криминалом и '
                                                     'становится идеальным домохозяином.',
                                             'id': 43692,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx125426-WeKnIVjCRNIC.png',
                                             'ru': 'Путь домохозяина',
                                             'score': '7.10'},
                                         {   'en': 'Handa-kun',
                                             'genres': 'Комедия, Школа',
                                             'hook': 'Гениальный каллиграф страдает паранойей, считая всеобщую любовь '
                                                     'заговорщической травлей.',
                                             'id': 32648,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21626-5jbbIK9DsmY8.jpg',
                                             'ru': 'Ханда-кун',
                                             'score': '7.00'},
                                         {   'en': 'Kaguya-sama: Love is War -Ultra Romantic-',
                                             'genres': 'Комедия, Романтика',
                                             'hook': 'Два гения элитной академии развязывают изощрённую '
                                                     'психологическую дуэль признаний.',
                                             'id': 43608,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx125367-1yuq9NFcQuLI.png',
                                             'ru': 'Госпожа Кагуя: В любви как на войне',
                                             'score': '8.90'},
                                         {   'en': 'BOCCHI THE ROCK!',
                                             'genres': 'Комедия, Музыка',
                                             'hook': 'Застенчивая Хитори Гото преодолевает социофобию с гитарой в '
                                                     'девичьей инди-группе.',
                                             'id': 47917,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx130003-HTDmeL4RGeJ4.png',
                                             'ru': 'Одинокий рокер!',
                                             'score': '8.70'},
                                         {   'en': 'Gabriel DropOut',
                                             'genres': 'Комедия, Сверхъестественное',
                                             'hook': 'Лучшая выпускница школы ангелов попадает на Землю и превращается '
                                                     'в заядлую геймершу.',
                                             'id': 33731,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21878-rfzDjP2gjxGR.jpg',
                                             'ru': 'Габриэль бросает школу',
                                             'score': '7.30'},
                                         {   'en': 'Non Non Biyori',
                                             'genres': 'Комедия, Повседневность',
                                             'hook': 'Четыре девочки наслаждаются беззаботными временами года в тихой '
                                                     'японской деревне.',
                                             'id': 17549,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx17549-ROdV36u4nWkU.png',
                                             'ru': 'Деревенская глубинка',
                                             'score': '7.80'},
                                         {   'en': 'Laid-Back Camp',
                                             'genres': 'Повседневность, Релакс',
                                             'hook': 'Одиночные походы с палаткой к подножию горы Фудзи и тепло костра '
                                                     'с горячим рамэном.',
                                             'id': 34798,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98444-Vzysp1EsrzgD.jpg',
                                             'ru': 'Лагерь на свежем воздухе',
                                             'score': '8.10'},
                                         {   'en': 'K-ON!',
                                             'genres': 'Комедия, Музыка',
                                             'hook': 'Четыре беззаботные школьницы спасают клуб легкой музыки '
                                                     'чаепитиями и роком.',
                                             'id': 5680,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5680-r3AI3Cwfv0Aq.png',
                                             'ru': 'Кэйон!',
                                             'score': '7.80'},
                                         {   'en': 'Lucky☆Star',
                                             'genres': 'Комедия, Отаку',
                                             'hook': 'Коната Идзуми и её подруги ведут бесконечные забавные дискуссии '
                                                     'о жизни и аниме.',
                                             'id': 1887,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1887-P36Pucd4qKji.png',
                                             'ru': 'Счастливая звезда',
                                             'score': '7.50'},
                                         {   'en': 'Azumanga Daioh',
                                             'genres': 'Комедия, Школа',
                                             'hook': 'Золотая классика абсурдной школьной комедии о вундеркинде Чиё и '
                                                     'её эксцентричных подругах.',
                                             'id': 66,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx66-ZqYQWl6LsfeI.png',
                                             'ru': 'Азуманга Дайо',
                                             'score': '7.90'},
                                         {   'en': 'Amagi Brilliant Park',
                                             'genres': 'Комедия, Магия',
                                             'hook': 'Самовлюблённый отличник спасает волшебный парк развлечений от '
                                                     'закрытия за 3 месяца.',
                                             'id': 22147,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20602-f6CfipBF44kV.png',
                                             'ru': 'Великолепный парк Амаги',
                                             'score': '7.20'},
                                         {   'en': 'Is the Order a Rabbit?',
                                             'genres': 'Комедия, Милота',
                                             'hook': 'Кокоа переезжает в кафе «Дом кролика» и находит милейших подруг.',
                                             'id': 21273,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20517-SNNUtav2knou.jpg',
                                             'ru': 'Заказывали кролика?',
                                             'score': '7.30'},
                                         {   'en': 'Girlfriend, Girlfriend',
                                             'genres': 'Комедия, Романтика',
                                             'hook': 'Прямолинейный старшеклассник с согласия обеих девушек начинает '
                                                     'открыто встречаться сразу с двумя.',
                                             'id': 43969,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx126192-3fFbZJFSwrHH.jpg',
                                             'ru': 'Мои девушки',
                                             'score': '6.30'},
                                         {   'en': 'Joshiraku',
                                             'genres': 'Комедия, Диалоги',
                                             'hook': 'Пять девушек-ракугок ведут остроумные разговоры обо всем на '
                                                     'свете за кулисами традиционного театра.',
                                             'id': 12679,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx12679-b7caRVFG2qkk.png',
                                             'ru': 'Дзёсираку',
                                             'score': '7.30'},
                                         {   'en': 'Sabage-bu!',
                                             'genres': 'Комедия, Пародия',
                                             'hook': 'Школьницы играют в страйкбол, используя самое богатое и '
                                                     'безжалостное воображение.',
                                             'id': 62287,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Клуб выживания!',
                                             'score': '7.20'},
                                         {   'en': 'Mitsudomoe',
                                             'genres': 'Комедия, Школа',
                                             'hook': 'Бедный учитель начальных классов сходит с ума от трех совершенно '
                                                     'невыносимых сестер Маруи.',
                                             'id': 51991,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Тройняшки',
                                             'score': '7.40'},
                                         {   'en': 'Plastic Neesan',
                                             'genres': 'Комедия, Ураган',
                                             'hook': 'Короткометражные безумные приключения трех участниц клуба сборки '
                                                     'пластиковых моделей.',
                                             'id': 80520,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Пластиковая сестрёнка',
                                             'score': '7.20'},
                                         {   'en': 'Beelzebub',
                                             'genres': 'Комедия, Драки',
                                             'hook': 'Свирепый хулиган Тацуми Ога случайно становится приемным отцом '
                                                     'для младенца-Владыки Демонов.',
                                             'id': 9513,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx9513-is6YiSgKbyQX.jpg',
                                             'ru': 'Вельзепуз',
                                             'score': '7.50'}],
                       'desc': 'Море отборного юмора, ярких персонажей и гарантированный заряд позитива:',
                       'key': 'pure_comedy',
                       'name': '😂 Отборные комедии и позитив',
                       'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx918-iOaeBVUn4uK7.jpg',
                       'shiki_genre': None,
                       'shiki_order': None,
                       'tags': '#комедия #пародия #позитив',
                       'title': 'Отборные комедии и позитив 😂'},
    'shonen_hype': {   'candidates': [   {   'en': 'Attack on Titan',
                                             'genres': 'Экшен, Драма',
                                             'hook': 'Человечество ведёт отчаянную войну за выживание против '
                                                     'гигантских титанов-людоедов.',
                                             'id': 16498,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16498-buvcRTBx4NSm.jpg',
                                             'ru': 'Атака титанов',
                                             'score': '8.50'},
                                         {   'en': 'Hunter x Hunter (2011)',
                                             'genres': 'Приключения, Сёнэн',
                                             'hook': 'Юный Гон Фрикс отправляется на смертоносный экзамен, чтобы найти '
                                                     'своего отца.',
                                             'id': 11061,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11061-y5gsT1hoHuHw.png',
                                             'ru': 'Охотник х Охотник',
                                             'score': '8.90'},
                                         {   'en': 'JUJUTSU KAISEN',
                                             'genres': 'Экшен, Мистика',
                                             'hook': 'Школьник поглощает палец короля проклятий Сукуны и вступает в '
                                                     'войну магов.',
                                             'id': 40748,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113415-LHBAeoZDIsnF.jpg',
                                             'ru': 'Магическая битва',
                                             'score': '8.40'},
                                         {   'en': 'Demon Slayer: Kimetsu no Yaiba',
                                             'genres': 'Экшен, Исторический',
                                             'hook': 'Тандзиро берёт в руки меч, чтобы отомстить демонам и вернуть '
                                                     'человечность сестре.',
                                             'id': 38000,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101922-WBsBl0ClmgYL.jpg',
                                             'ru': 'Клинок, рассекающий демонов',
                                             'score': '8.30'},
                                         {   'en': 'Chainsaw Man',
                                             'genres': 'Экшен, Тёмное фэнтези',
                                             'hook': 'Дэндзи заключает контракт с демоническим псом и распиливает '
                                                     'чудовищ бензопилами.',
                                             'id': 44511,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx127230-DdP4vAdssLoz.png',
                                             'ru': 'Человек-бензопила',
                                             'score': '8.30'},
                                         {   'en': 'BLEACH: Thousand-Year Blood War',
                                             'genres': 'Экшен, Сверхъестественное',
                                             'hook': 'Финальная битва синигами Общества Душ против вернувшейся армии '
                                                     'квинси.',
                                             'id': 41467,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx116674-p3zK4PUX2Aag.jpg',
                                             'ru': 'Блич: Тысячелетняя кровавая война',
                                             'score': '8.80'},
                                         {   'en': 'Naruto: Shippuden',
                                             'genres': 'Экшен, Ниндзя',
                                             'hook': 'Повзрослевший Наруто сражается с организацией Акацуки ради '
                                                     'спасения друга Саскэ.',
                                             'id': 1735,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1735-kGfVm0YqCPcu.png',
                                             'ru': 'Наруто: Ураганные хроники',
                                             'score': '8.20'},
                                         {   'en': 'ONE PIECE',
                                             'genres': 'Приключения, Экшен',
                                             'hook': 'Манки Д. Луффи с командой Соломенной Шляпы ищет величайшее '
                                                     'сокровище мира.',
                                             'id': 21,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21-ELSYx3yMPcKM.jpg',
                                             'ru': 'Ван-Пис',
                                             'score': '8.70'},
                                         {   'en': 'My Hero Academia',
                                             'genres': 'Экшен, Супергерои',
                                             'hook': 'Бессильный мальчик получает мощь величайшего героя Всемогущего и '
                                                     'поступает в академию.',
                                             'id': 31964,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21459-nYh85uj2Fuwr.jpg',
                                             'ru': 'Моя геройская академия',
                                             'score': '7.70'},
                                         {   'en': 'Black Clover',
                                             'genres': 'Магия, Экшен',
                                             'hook': 'Парень без капли магии получает антимагический гримуар, стремясь '
                                                     'стать Королём магов.',
                                             'id': 34572,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx97940-fyh8o7gNbha0.png',
                                             'ru': 'Чёрный клевер',
                                             'score': '7.90'},
                                         {   'en': 'Solo Leveling',
                                             'genres': 'Экшен, Фэнтези',
                                             'hook': 'Слабейший охотник Сон Джин-у пробуждает секретную систему '
                                                     'прокачки в подземельях.',
                                             'id': 52299,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx151807-it355ZgzquUd.png',
                                             'ru': 'Поднятие уровня в одиночку',
                                             'score': '8.00'},
                                         {   'en': 'Kaiju No. 8',
                                             'genres': 'Экшен, Sci-Fi',
                                             'hook': '32-летний уборщик останков монстров случайно обретает силу '
                                                     'могучего Кайдзю.',
                                             'id': 52588,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx153288-25FBfFJzEQ5O.jpg',
                                             'ru': 'Кайдзю номер восемь',
                                             'score': '8.10'},
                                         {   'en': 'Mob Psycho 100',
                                             'genres': 'Экшен, Комедия',
                                             'hook': 'Школьник с колоссальными телекинетическими силами сдерживает '
                                                     'эмоции ради обычной жизни.',
                                             'id': 32182,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21507-6YUSbh2m0N1p.jpg',
                                             'ru': 'Моб Психо 100',
                                             'score': '8.40'},
                                         {   'en': 'Fullmetal Alchemist: Brotherhood',
                                             'genres': 'Фэнтези, Приключения',
                                             'hook': 'Братья Элрики ищут философский камень, стремясь искупить '
                                                     'запретный грех.',
                                             'id': 5114,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5114-nSWCgQlmOMtj.jpg',
                                             'ru': 'Стальной алхимик: Братство',
                                             'score': '9.00'},
                                         {   'en': "JoJo's Bizarre Adventure: Stardust Crusaders",
                                             'genres': 'Экшен, Приключения',
                                             'hook': 'Джотаро Куджо и команда стенд-юзеров отправляются в Египет '
                                                     'уничтожить Дио.',
                                             'id': 20899,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20474-xuqem5GBlBtb.jpg',
                                             'ru': 'ДжоДжо: Рыцари звёздной пыли',
                                             'score': '7.90'},
                                         {   'en': "JoJo's Bizarre Adventure: Golden Wind",
                                             'genres': 'Экшен, Криминал',
                                             'hook': 'Джорно Джованна пробивается на вершину неаполитанской мафии ради '
                                                     'мечты.',
                                             'id': 37991,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx102883-S9KzdMJhDswJ.png',
                                             'ru': 'ДжоДжо: Золотой ветер',
                                             'score': '8.50'},
                                         {   'en': 'Fire Force',
                                             'genres': 'Экшен, Сверхъестественное',
                                             'hook': 'Особые пожарные с пирокинезом тушат людей, превратившихся в '
                                                     'живое пламя.',
                                             'id': 38671,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105310-2PKUvoaA6fTn.jpg',
                                             'ru': 'Пламенная бригада пожарных',
                                             'score': '7.60'},
                                         {   'en': 'Tokyo Revengers',
                                             'genres': 'Экшен, Драма',
                                             'hook': 'Неудачник перемещается на 12 лет назад, чтобы спасти первую '
                                                     'любовь от гибели в банде.',
                                             'id': 42249,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx120120-cWDmnmeEntSe.jpg',
                                             'ru': 'Токийские мстители',
                                             'score': '7.70'},
                                         {   'en': 'WIND BREAKER',
                                             'genres': 'Экшен, Школа',
                                             'hook': 'Одинокий боец поступает в школу хулиганов, защищающих покой '
                                                     'родного города.',
                                             'id': 54900,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx163270-wboZJp0ybwVK.jpg',
                                             'ru': 'Ветролом',
                                             'score': '7.70'},
                                         {   'en': 'MASHLE: MAGIC AND MUSCLES',
                                             'genres': 'Комедия, Экшен',
                                             'hook': 'Парень без магии качает мышцы до абсурдного уровня, круша '
                                                     'надменных магов.',
                                             'id': 52211,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx151801-XxVf22Le6C8o.png',
                                             'ru': 'Магия и мускулы',
                                             'score': '7.60'},
                                         {   'en': 'Hell’s Paradise',
                                             'genres': 'Экшен, Тёмное фэнтези',
                                             'hook': 'Приговорённый к казни ниндзя Габимару ищет эликсир бессмертия на '
                                                     'острове монстров.',
                                             'id': 46569,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx128893-Gc2t8b8M0mVu.jpg',
                                             'ru': 'Адский рай',
                                             'score': '8.00'},
                                         {   'en': 'Undead Unluck',
                                             'genres': 'Экшен, Комедия',
                                             'hook': 'Бессмертный зомби и девушка, приносящая несчастья, бросают вызов '
                                                     'правилам мира.',
                                             'id': 52741,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154116-3ydDI9hhvPgw.png',
                                             'ru': 'Нежить и Неудача',
                                             'score': '7.60'},
                                         {   'en': 'BLUE LOCK',
                                             'genres': 'Спорт, Триллер',
                                             'hook': '300 молодых нападающих борются в эгоистичной королевской битве '
                                                     'за звание лучшего.',
                                             'id': 49596,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx137822-U8naszP96vzC.png',
                                             'ru': 'Синяя тюрьма: Блю Лок',
                                             'score': '8.00'},
                                         {   'en': 'HAIKYU!!',
                                             'genres': 'Спорт, Драма',
                                             'hook': 'Низкорослый Сёё Хината взмывает над сеткой, ведя команду '
                                                     'Карасуно к вершине.',
                                             'id': 20583,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20464-ooZUyBe4ptp9.png',
                                             'ru': 'Волейбол!!',
                                             'score': '8.40'},
                                         {   'en': 'Dororo',
                                             'genres': 'Экшен, Исторический',
                                             'hook': 'Хяккимару истребляет 12 демонов, чтобы вернуть украденные при '
                                                     'рождении органы.',
                                             'id': 37520,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101347-TGaDwEYqLfm1.jpg',
                                             'ru': 'Дороро',
                                             'score': '8.10'},
                                         {   'en': 'Rurouni Kenshin',
                                             'genres': 'Исторический, Самураи',
                                             'hook': 'Легендарный мечник-убийца даёт клятву никого не убивать, защищая '
                                                     'слабых мечом с обратным лезвием.',
                                             'id': 45,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx45-DEFgZRCxiGmF.png',
                                             'ru': 'Бродяга Кэнсин',
                                             'score': '7.90'},
                                         {   'en': 'Soul Eater',
                                             'genres': 'Экшен, Фэнтези',
                                             'hook': 'Студенты оружейной академии шинигами собирают души злых людей '
                                                     'ради создания Косы Смерти.',
                                             'id': 3588,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx3588-fSMggQoFSbUI.png',
                                             'ru': 'Пожиратель душ',
                                             'score': '7.70'},
                                         {   'en': 'Noragami',
                                             'genres': 'Экшен, Мистика',
                                             'hook': 'Бродячий бог Ято выполняет любые поручения за 5 иен, мечтая о '
                                                     'собственном храме.',
                                             'id': 39636,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Бездомный бог',
                                             'score': '7.95'},
                                         {   'en': 'Kill la Kill',
                                             'genres': 'Экшен, Комедия',
                                             'hook': 'Рюко Матой с гигантской половиной ножниц сражается с элитным '
                                                     'школьным советом.',
                                             'id': 18679,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b18679-lbkq7iYESoFW.png',
                                             'ru': 'Убей или умри',
                                             'score': '7.90'},
                                         {   'en': 'Bleach',
                                             'genres': 'Экшен, Синигами',
                                             'hook': 'Ичиго Куросаки случайно получает силы проводника душ и защищает '
                                                     'мир живых от Пустых.',
                                             'id': 269,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx269-d2GmRkJbMopq.png',
                                             'ru': 'Блич',
                                             'score': '7.90'},
                                         {   'en': 'Fairy Tail',
                                             'genres': 'Фэнтези, Магия',
                                             'hook': 'Нацу Драгнил и гильдия волшебников Хвост Феи сражаются за друзей '
                                                     'в грандиозных битвах.',
                                             'id': 83499,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg',
                                             'ru': 'Хвост Феи',
                                             'score': '7.60'},
                                         {   'en': 'Dragon Ball Z',
                                             'genres': 'Экшен, Сверхсилы',
                                             'hook': 'Сон Гоку и воины Z защищают Землю от инопланетных захватчиков '
                                                     'Саянов и тирана Фризы.',
                                             'id': 813,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx813-ZhnFNOeCU5dQ.png',
                                             'ru': 'Драконий жемчуг Зет',
                                             'score': '8.00'},
                                         {   'en': 'D.Gray-man',
                                             'genres': 'Экшен, Мистика',
                                             'hook': 'Аллен Уолкер и экзорцисты Черного Ордена сражаются с '
                                                     'механическими демонами Акума.',
                                             'id': 1482,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1482-6jc8ZVSmHuLo.jpg',
                                             'ru': 'Ди Грэй-мен',
                                             'score': '7.60'},
                                         {   'en': 'REBORN!',
                                             'genres': 'Экшен, Сёнэн',
                                             'hook': 'Неуклюжий школьник Цуна становится наследником мафиозной семьи '
                                                     'Вонгола под надзором Реборна.',
                                             'id': 1604,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1604-W2q38L4OCGLI.png',
                                             'ru': 'Учитель-киллер Реборн!',
                                             'score': '7.70'},
                                         {   'en': 'Hawk no Onayami Soudanshitsu Special',
                                             'genres': 'Фэнтези, Экшен',
                                             'hook': 'Капитан Мелиодас собирает легендарных рыцарей-изгоев, чтобы '
                                                     'спасти королевство Лионес.',
                                             'id': 54778,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154197-yJZMgNynqQtW.jpg',
                                             'ru': 'Семь смертных грехов',
                                             'score': '4.60'},
                                         {   'en': 'InuYasha',
                                             'genres': 'Фэнтези, Исторический',
                                             'hook': 'Школьница Кагомэ попадает в средневековую Японию и ищет осколки '
                                                     'Камня Душ с полудемоном Инуясей.',
                                             'id': 249,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx249-jVBkyLnBvnRE.png',
                                             'ru': 'Инуяся',
                                             'score': '7.70'},
                                         {   'en': 'Yu Yu Hakusho: Ghostfiles',
                                             'genres': 'Экшен, Мистика',
                                             'hook': 'Хулиган Юсукэ погибает, спасая ребёнка, и становится сыщиком '
                                                     'мира мёртвых.',
                                             'id': 392,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx392-z90299zIvYmx.png',
                                             'ru': 'Отчёт об буйстве духов',
                                             'score': '8.30'},
                                         {   'en': 'Akame ga Kill!',
                                             'genres': 'Экшен, Тёмное фэнтези',
                                             'hook': 'Отряд наёмных убийц «Ночной Рейд» истребляет коррумпированную '
                                                     'знать столицы.',
                                             'id': 22199,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20613-HXHpec4bemk5.jpg',
                                             'ru': 'Убийца Акаме!',
                                             'score': '7.30'},
                                         {   'en': 'Seraph of the End: Vampire Reign',
                                             'genres': 'Экшен, Вампиры',
                                             'hook': 'Человечество порабощено вампирами, но отряд «Лунные демоны» '
                                                     'наносит ответный удар.',
                                             'id': 26243,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20829-pgsXVjrfyI5V.png',
                                             'ru': 'Последний Серафим',
                                             'score': '7.30'},
                                         {   'en': 'Black Bullet',
                                             'genres': 'Экшен, Sci-Fi',
                                             'hook': 'Охотники на вирусных монстров Гастреа сражаются бок о бок с '
                                                     'Проклятыми Детьми.',
                                             'id': 20787,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20457-ftrNiYhZzgoY.jpg',
                                             'ru': 'Чёрная пуля',
                                             'score': '6.70'},
                                         {   'en': "Darwin's Game",
                                             'genres': 'Экшен, Выживание',
                                             'hook': 'Школьник скачивает мобильную игру и втягивается в смертельные '
                                                     'дуэли за жизнь.',
                                             'id': 38656,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105190-lSoQNlnMF6UP.jpg',
                                             'ru': 'Игра Дарвина',
                                             'score': '7.00'},
                                         {   'en': 'Tokyo Ravens',
                                             'genres': 'Экшен, Магия',
                                             'hook': 'Молодые оммёдзи защищают современный Токио от духовных '
                                                     'катастроф.',
                                             'id': 16011,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16011-orxVpks3jG9U.jpg',
                                             'ru': 'Токийские вороны',
                                             'score': '7.10'},
                                         {   'en': 'Toriko',
                                             'genres': 'Экшен, Гурман',
                                             'hook': 'Охотник за деликатесами Торико сражается с исполинскими '
                                                     'чудовищами ради идеального меню.',
                                             'id': 10033,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx10033-V7xnlgAVtaVR.jpg',
                                             'ru': 'Торико',
                                             'score': '6.90'},
                                         {   'en': 'Shaman King',
                                             'genres': 'Экшен, Духи',
                                             'hook': 'Йо Асакура с духом самурая Амидамару участвует в Битве Шаманов '
                                                     'за титул Короля.',
                                             'id': 154,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154-hSYv4EtcBE1p.png',
                                             'ru': 'Шаман Кинг',
                                             'score': '7.40'},
                                         {   'en': 'Blood Lad',
                                             'genres': 'Экшен, Вампиры',
                                             'hook': 'Вампир-отаку Стаз пытается воскресить погибшую в Аду '
                                                     'человеческую девушку Фуюдзи.',
                                             'id': 11633,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11633-vIjtabJq64Xt.jpg',
                                             'ru': 'Кровавый парень',
                                             'score': '6.90'},
                                         {   'en': 'The God of High School',
                                             'genres': 'Экшен, Боевые искусства',
                                             'hook': 'Турнир сильнейших бойцов старших школ за исполнение любого '
                                                     'желания перерастает в битву богов.',
                                             'id': 41353,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx116006-Wt8JSA1ZQxlM.png',
                                             'ru': 'Царь горы',
                                             'score': '7.00'},
                                         {   'en': 'Air Gear',
                                             'genres': 'Спорт, Экшен',
                                             'hook': 'Икки покоряет улицы на роликах с мотором Air Treck, стремясь к '
                                                     'Небесному Регалии.',
                                             'id': 857,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/b857-0pbF6kMJpUeL.png',
                                             'ru': 'Эйр Гир',
                                             'score': '7.00'},
                                         {   'en': 'GetBackers',
                                             'genres': 'Экшен, Сверхсилы',
                                             'hook': 'Мидо Бан с глазом иллюзий и Гиндзи Амано со 100 000 вольт '
                                                     'электричества возвращают любые вещи.',
                                             'id': 132,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx132-DBhi3KQASjLU.png',
                                             'ru': 'Агентство по возврату долгов',
                                             'score': '7.10'},
                                         {   'en': 'Black God',
                                             'genres': 'Экшен, Боевые искусства',
                                             'hook': 'Парень заключает контракт с хранительницей баланса Куро в битве '
                                                     'за потоки жизненной энергии Доппель.',
                                             'id': 5079,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx5079-GGC5BR9xIiE0.jpg',
                                             'ru': 'Куроками',
                                             'score': '6.60'},
                                         {   'en': 'Claymore',
                                             'genres': 'Экшен, Тёмное фэнтези',
                                             'hook': 'Клэр раскрывает силу монстра Йома ради мести за наставницу '
                                                     'Терезу.',
                                             'id': 1818,
                                             'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1818-KieLJv0qo3mO.jpg',
                                             'ru': 'Клеймор: Воительницы',
                                             'score': '7.40'}],
                       'desc': 'Адреналиновые противостояния, несгибаемая воля и легендарные битвы:',
                       'key': 'shonen_hype',
                       'name': '🔥 Сёнэн, ураганный экшен и культовые битвы',
                       'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16498-buvcRTBx4NSm.jpg',
                       'shiki_genre': None,
                       'shiki_order': None,
                       'tags': '#сёнэн #экшен #топ_битвы',
                       'title': 'Сёнэн, ураганный экшен и культовые битвы 🔥'},
    'soul_romance': {   'candidates': [   {   'en': 'Kaguya-sama wa Kokurasetai: Tensaitachi no Renai Zunousen',
                                              'genres': 'Комедия, Романтика',
                                              'hook': 'Президенты элитного студсовета ведут войну умов за первое '
                                                      'признание в чувствах.',
                                              'id': 37999,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101921-ufrjLzhSz7L1.jpg',
                                              'ru': 'Госпожа Кагуя: В любви как на войне',
                                              'score': '8.30'},
                                          {   'en': 'Horimiya',
                                              'genres': 'Школа, Романтика',
                                              'hook': 'Два разных старшеклассника открывают друг другу свои настоящие '
                                                      'тайные стороны.',
                                              'id': 42897,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx124080-3i22mRVPBS0T.jpg',
                                              'ru': 'Хоримия',
                                              'score': '8.10'},
                                          {   'en': 'CLANNAD: After Story',
                                              'genres': 'Драма, Романтика',
                                              'hook': 'Трогательная история взросления, семейных ценностей и настоящей '
                                                      'вечной любви.',
                                              'id': 4181,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx4181-zUKE7BZC62OF.png',
                                              'ru': 'Кланнад: Продолжение истории',
                                              'score': '8.80'},
                                          {   'en': 'Koe no Katachi',
                                              'genres': 'Драма, Школа',
                                              'hook': 'Бывший задира ищет искупления перед глухой одноклассницей.',
                                              'id': 28851,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20954-sYRfE5jQRtSB.jpg',
                                              'ru': 'Форма голоса',
                                              'score': '8.80'},
                                          {   'en': 'Shigatsu wa Kimi no Uso',
                                              'genres': 'Музыка, Драма',
                                              'hook': 'Скрипачка-бунтарка возвращает юному пианисту страсть к музыке и '
                                                      'жизни.',
                                              'id': 23273,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20665-TLgkL8T8IRFd.png',
                                              'ru': 'Твоя апрельская ложь',
                                              'score': '8.40'},
                                          {   'en': 'Toradora!',
                                              'genres': 'Комедия, Романтика',
                                              'hook': 'Грозный с виду парень и миниатюрная Тигрица помогают друг другу '
                                                      'в делах любви.',
                                              'id': 4224,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx4224-PXVMBLNwy2aF.jpg',
                                              'ru': 'Торадора!',
                                              'score': '7.80'},
                                          {   'en': 'Seishun Buta Yarou wa Bunny Girl Senpai no Yume wo Minai',
                                              'genres': 'Мистика, Романтика',
                                              'hook': 'Сакута помогает актрисе в костюме зайки, которую перестают '
                                                      'замечать окружающие.',
                                              'id': 37450,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101291-wfEdgPqtfU0l.jpg',
                                              'ru': 'Этот глупый свин не понимает мечту девочки-зайки',
                                              'score': '8.10'},
                                          {   'en': 'Kimi ni Todoke',
                                              'genres': 'Школа, Романтика',
                                              'hook': 'Скромная девушка Савако учится общаться с миром благодаря '
                                                      'доброму однокласснику.',
                                              'id': 6045,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx6045-JujXjoWtslUM.jpg',
                                              'ru': 'Дотянуться до тебя',
                                              'score': '7.90'},
                                          {   'en': 'Boku no Kokoro no Yabai Yatsu',
                                              'genres': 'Комедия, Романтика',
                                              'hook': 'Мрачный интроверт постепенно сближается с жизнерадостной '
                                                      'школьной красавицей.',
                                              'id': 52578,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx153152-Xnwmx7wuoIWV.jpg',
                                              'ru': 'Опасность в моем сердце',
                                              'score': '8.10'},
                                          {   'en': 'Go-toubun no Hanayome',
                                              'genres': 'Гарем, Романтика',
                                              'hook': 'Бедный отличник нанимается репетитором к пяти непокорным '
                                                      'сестрам-близняшкам.',
                                              'id': 38101,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx103572-cchriAdH95cQ.png',
                                              'ru': 'Пять невест',
                                              'score': '7.60'},
                                          {   'en': 'Sakurasou no Pet na Kanojo',
                                              'genres': 'Комедия, Драма',
                                              'hook': 'Жизнь в общежитии одаренных чудаков учит мечтать и не сдаваться '
                                                      'перед трудностями.',
                                              'id': 13759,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx13759-xNf0gJK4Axt2.jpg',
                                              'ru': 'Кошечка из Сакурасо',
                                              'score': '7.80'},
                                          {   'en': 'Yahari Ore no Seishun Love Come wa Machigatteiru. Zoku: Kitto, '
                                                    'Onnanoko wa Osatou to Spice to Suteki na Nanika de Dekiteiru',
                                              'genres': 'Драма, Романтика',
                                              'hook': 'Клуб служения помогает старшеклассникам разрешать их '
                                                      'эмоциональные кризисы.',
                                              'id': 33161,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21769-ZBoT6szJKGZv.jpg',
                                              'ru': 'Как и ожидалось, моя школьная жизнь не задалась',
                                              'score': '7.80'},
                                          {   'en': 'Your Name.',
                                              'genres': 'Drama, Romance, Supernatural',
                                              'hook': 'Шедевр Макото Синкая о мистической связи двух подростков сквозь '
                                                      'время.',
                                              'id': 32281,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21519-SUo3ZQuCbYhJ.png',
                                              'ru': 'Твоё имя',
                                              'score': '8.82'},
                                          {   'en': 'Weathering With You',
                                              'genres': 'Drama, Romance, Slice of Life',
                                              'hook': 'Парень встречает девушку, способную разгонять тучи над Токио '
                                                      'силой молитвы.',
                                              'id': 38826,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx106286-5COcpd0J9VbL.png',
                                              'ru': 'Дитя погоды',
                                              'score': '8.27'},
                                          {   'en': 'Violet Evergarden',
                                              'genres': 'Drama, Fantasy, Slice of Life',
                                              'hook': 'Вайолет учится любить и сопереживать, помогая людям выражать '
                                                      'чувства в письмах.',
                                              'id': 33352,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21827-ubzq619ZA2E9.png',
                                              'ru': 'Вайолет Эвергарден',
                                              'score': '8.69'},
                                          {   'en': 'Golden Time',
                                              'genres': 'Drama, Romance',
                                              'hook': 'Студенческая жизнь, потеря памяти и искренний роман с '
                                                      'темпераментной Коко.',
                                              'id': 17895,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx17895-M8yjOyMxHf5X.jpg',
                                              'ru': 'Золотая пора',
                                              'score': '7.74'},
                                          {   'en': 'Wotakoi: Love is Hard for Otaku',
                                              'genres': 'Comedy, Romance, Slice of Life',
                                              'hook': 'Уютная и жизненная офисная романтика взрослых геймеров и '
                                                      'анимешников.',
                                              'id': 35968,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx99578-oO5KChtfhzln.png',
                                              'ru': 'Так сложно любить отаку',
                                              'score': '7.91'},
                                          {   'en': 'Fruits Basket (2019)',
                                              'genres': 'Comedy, Drama, Romance',
                                              'hook': 'Добрая Тору исцеляет сердца членов семьи Сома, страдающих от '
                                                      'проклятия зодиака.',
                                              'id': 38680,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx105334-AZwEdMu4KFtV.jpg',
                                              'ru': 'Корзинка фруктов (2019)',
                                              'score': '8.2'},
                                          {   'en': 'NANA',
                                              'genres': 'Drama, Music, Romance',
                                              'hook': 'Глубокая и правдивая история о любви, дружбе, рок-музыке и '
                                                      'взрослении в Токио.',
                                              'id': 877,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx877-6BUYEWp8By8j.png',
                                              'ru': 'Нана',
                                              'score': '8.57'},
                                          {   'en': 'Anohana: The Flower We Saw That Day',
                                              'genres': 'Drama, Romance, Slice of Life',
                                              'hook': 'Призрак погибшей девочки собирает распавшуюся компанию друзей '
                                                      'детства.',
                                              'id': 9989,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx9989-hImMg6kCMm6I.jpg',
                                              'ru': 'Невиданный цветок',
                                              'score': '8.28'},
                                          {   'en': 'Maid-Sama!',
                                              'genres': 'Comedy, Drama, Romance',
                                              'hook': 'Популярный красавец узнает тайную подработку строгой '
                                                      'президентши студсовета.',
                                              'id': 7054,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx7054-GW4D7VAZG19W.png',
                                              'ru': 'Президент студсовета — горничная!',
                                              'score': '7.98'},
                                          {   'en': 'My Dress-Up Darling',
                                              'genres': 'Comedy, Ecchi, Romance',
                                              'hook': 'Скромный мастер кукол и яркая гяру объединяются ради создания '
                                                      'косплея.',
                                              'id': 48736,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx132405-qP7FQYGmNI3d.jpg',
                                              'ru': 'Эта фарфоровая кукла влюбилась',
                                              'score': '8.13'},
                                          {   'en': 'Lovely Complex',
                                              'genres': 'Comedy, Romance, Slice of Life',
                                              'hook': 'Высокая девушка и низкий парень проходят путь от взаимных '
                                                      'подколов до любви.',
                                              'id': 2034,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2034-erjg6gzDetAp.png',
                                              'ru': 'Трогательный комплекс',
                                              'score': '8.03'},
                                          {   'en': 'Kamisama Kiss',
                                              'genres': 'Comedy, Fantasy, Romance',
                                              'hook': 'Школьница случайно становится богиней храма и встречает '
                                                      'лиса-хранителя Томоэ.',
                                              'id': 14713,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx14713-RyZ7bA7CdvGw.jpg',
                                              'ru': 'Очень приятно, Бог',
                                              'score': '8.13'},
                                          {   'en': 'Blue Spring Ride',
                                              'genres': 'Drama, Romance, Slice of Life',
                                              'hook': 'Встреча первой школьной любви спустя годы после взаимных '
                                                      'перемен.',
                                              'id': 21995,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20596-fJdMHV8xRMgY.png',
                                              'ru': 'Неудержимая юность',
                                              'score': '7.63'},
                                          {   'en': 'Orange',
                                              'genres': 'Drama, Romance, Supernatural',
                                              'hook': 'Письма из будущего помогают друзьям спасти одноклассника от '
                                                      'трагедии.',
                                              'id': 32729,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21647-zMUXNhcVyRyv.png',
                                              'ru': 'Орендж',
                                              'score': '7.63'},
                                          {   'en': 'Tsukigakirei',
                                              'genres': 'Drama, Romance, Slice of Life',
                                              'hook': 'Невероятно нежная и реалистичная история первой влюбленности '
                                                      'скромных подростков.',
                                              'id': 34822,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98202-H6RtsIMZPALF.png',
                                              'ru': 'Прекрасна, как Луна',
                                              'score': '8.02'},
                                          {   'en': 'ReLIFE',
                                              'genres': 'Comedy, Drama, Romance',
                                              'hook': '27-летний безработный получает шанс помолодеть на 10 лет и '
                                                      'исправить ошибки.',
                                              'id': 30015,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21049-4AHSLeiDE9eg.png',
                                              'ru': 'Повторная жизнь',
                                              'score': '7.96'},
                                          {   'en': 'Romantic Killer',
                                              'genres': 'Comedy, Romance',
                                              'hook': 'Геймерша борется с назойливым духом, пытающимся насильно '
                                                      'устроить ей свидания.',
                                              'id': 52865,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx153930-uTRxaIcNa26E.jpg',
                                              'ru': 'Романтический убийца',
                                              'score': '7.9'},
                                          {   'en': 'Plastic Memories',
                                              'genres': 'Drama, Romance, Sci-Fi',
                                              'hook': 'Трогательная история любви к андроиду-гифтии с ограниченным '
                                                      'сроком службы.',
                                              'id': 27775,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20872-j5PBzzVtrYDM.jpg',
                                              'ru': 'Пластиковые воспоминания',
                                              'score': '7.92'},
                                          {   'en': 'I Want to Eat Your Pancreas',
                                              'genres': 'Drama, Romance, Slice of Life',
                                              'hook': 'Замкнутый парень узнает тайну смертельно больной жизнерадостной '
                                                      'одноклассницы.',
                                              'id': 36098,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx99750-pNyly9d3MEgV.jpg',
                                              'ru': 'Я хочу съесть твою поджелудочную',
                                              'score': '8.56'},
                                          {   'en': 'Insomniacs After School',
                                              'genres': 'Romance, Slice of Life',
                                              'hook': 'Два страдающих бессонницей подростка находят покой в школьной '
                                                      'обсерватории.',
                                              'id': 50796,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx143653-uq3motvR9kb4.png',
                                              'ru': 'Бессонница после школы',
                                              'score': '8.08'},
                                          {   'en': 'My Love Story with Yamada-kun at Lv999',
                                              'genres': 'Comedy, Drama, Romance',
                                              'hook': 'Брошенная девушка встречает хладнокровного про-геймера в '
                                                      'онлайн-игре.',
                                              'id': 53126,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154965-vZbBRjtmLp7S.jpg',
                                              'ru': 'Моя любовь девятьсот девяносто девятого уровня к Ямаде',
                                              'score': '7.75'},
                                          {   'en': 'Kono Oto Tomare!: Sounds of Life',
                                              'genres': 'Drama, Music, Romance',
                                              'hook': 'Школьные хулиганы и музыканты возрождают традиционный клуб игры '
                                                      'на кото.',
                                              'id': 38080,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx103302-RVGwGRDGdMQq.jpg',
                                              'ru': 'Задержи этот звук!',
                                              'score': '7.94'},
                                          {   'en': 'Bloom Into You',
                                              'genres': 'Drama, Romance, Slice of Life',
                                              'hook': 'Глубокая психологическая драма о поиске своего истинного '
                                                      'чувства.',
                                              'id': 37786,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/nx101573-Gql3Q3UX1jcu.jpg',
                                              'ru': 'В конечном счёте я стану твоей',
                                              'score': '7.88'},
                                          {   'en': 'Fruits Basket The Final Season',
                                              'genres': 'Драма, Романтика',
                                              'hook': 'Тору Хонда разрушает древнее проклятие семьи Сома ценой '
                                                      'искренней доброты.',
                                              'id': 42938,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx124194-TJlqMMR7BGn9.jpg',
                                              'ru': 'Корзинка фруктов: Финал',
                                              'score': '8.90'},
                                          {   'en': 'Josee, the Tiger and the Fish',
                                              'genres': 'Романтика, Драма',
                                              'hook': 'Студент-океанолог становится помощником прикованной к креслу '
                                                      'мечтательной девушки.',
                                              'id': 40787,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113596-LKA0bYJGjLnB.jpg',
                                              'ru': 'Жозе, тигр и рыба',
                                              'score': '8.30'},
                                          {   'en': 'The Tunnel to Summer, the Exit of Goodbyes',
                                              'genres': 'Фэнтези, Романтика',
                                              'hook': 'Два школьника исследуют туннель Урасима, где время течёт иначе, '
                                                      'в обмен на исполнение желаний.',
                                              'id': 50593,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx142769-kNyyqpwC9gGV.jpg',
                                              'ru': 'Туннель в лето, выход прощаний',
                                              'score': '8.00'},
                                          {   'en': 'Honey and Clover',
                                              'genres': 'Драма, Романтика',
                                              'hook': 'Тёплая и меланхоличная сага о студентах художественного '
                                                      'колледжа, поиске себя и любви.',
                                              'id': 16,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx16-S9k8qahNXoYP.jpg',
                                              'ru': 'Мёд и клевер',
                                              'score': '7.60'},
                                          {   'en': 'Nodame Cantabile: Nodame to Chiaki no Umi Monogatari',
                                              'genres': 'Музыка, Комедия',
                                              'hook': 'Строгий будущий дирижёр и хаотичная гениальная пианистка '
                                                      'покоряют мировую классику.',
                                              'id': 3965,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/medium/3965.jpg',
                                              'ru': 'Нодамэ Кантабиле',
                                              'score': '6.90'},
                                          {   'en': 'Kokoro Connect',
                                              'genres': 'Драма, Сверхъестественное',
                                              'hook': 'Пятеро участников школьного клуба переживают обмен телами и '
                                                      'раскрытие самых стыдных тайн.',
                                              'id': 11887,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx11887-ypZTwcRqopiL.jpg',
                                              'ru': 'Связь сердец',
                                              'score': '7.50'},
                                          {   'en': 'Clannad',
                                              'genres': 'Драма, Школа',
                                              'hook': 'Томоя помогает замкнутой Нагисе возродить школьный драмкружок и '
                                                      'обретает семью.',
                                              'id': 2167,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2167-pSDBcyc0vjej.jpg',
                                              'ru': 'Кланнад (1 сезон)',
                                              'score': '7.70'},
                                          {   'en': 'Kanon',
                                              'genres': 'Драма, Романтика',
                                              'hook': 'Парень возвращается в снежный город детства и восстанавливает '
                                                      'забытые воспоминания девушек.',
                                              'id': 144,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx144-YdWsrDNssRIX.png',
                                              'ru': 'Канон',
                                              'score': '6.50'},
                                          {   'en': 'Kiznaiver',
                                              'genres': 'Драма, Sci-Fi',
                                              'hook': 'Семь незнакомых подростков связаны общей физической и душевной '
                                                      'болью ради мира.',
                                              'id': 31798,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx21421-5y8ryXsMB7aJ.jpg',
                                              'ru': 'Кизнайвер',
                                              'score': '7.20'},
                                          {   'en': 'Just Because!',
                                              'genres': 'Романтика, Школа',
                                              'hook': 'Возвращение старого друга переворачивает размеренную жизнь '
                                                      'выпускников школы.',
                                              'id': 35639,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx98820-EVHeNEUOWkh3.jpg',
                                              'ru': 'Просто потому что!',
                                              'score': '7.00'},
                                          {   'en': 'True Tears',
                                              'genres': 'Романтика, Драма',
                                              'hook': 'Сложный любовный треугольник юноши-художника и девушки, '
                                                      'разучившейся плакать.',
                                              'id': 2129,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2129-5TX1vWYYe2MT.png',
                                              'ru': 'Настоящие слёзы',
                                              'score': '6.80'},
                                          {   'en': 'ef ~ A Tale of Memories',
                                              'genres': 'Драма, Романтика',
                                              'hook': 'Переплетение драматических любовных историй сквозь потерю '
                                                      'памяти и расстояния.',
                                              'id': 2924,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx2924-MXCrAa1KAdzH.jpg',
                                              'ru': 'Эф — история воспоминаний',
                                              'score': '7.50'},
                                          {   'en': 'Rent-a-Girlfriend',
                                              'genres': 'Романтика, Комедия',
                                              'hook': 'Брошенный студент берет напрокат безупречную девушку Тидзуру '
                                                      'Итиносэ и влюбляется.',
                                              'id': 40839,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx113813-SnljeXpU3Pw7.jpg',
                                              'ru': 'Девушка напрокат',
                                              'score': '6.50'},
                                          {   'en': 'Nisekoi',
                                              'genres': 'Романтика, Комедия',
                                              'hook': 'Сын босса якудзы и дочь главаря мафии вынуждены притворяться '
                                                      'парой во избежание войны.',
                                              'id': 18897,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx18897-G2Fx2ZACsXBU.jpg',
                                              'ru': 'Притворная любовь',
                                              'score': '7.30'},
                                          {   'en': "Monthly Girls' Nozaki-kun",
                                              'genres': 'Романтика, Комедия',
                                              'hook': 'Тиё Сакура признается в любви двухметровому мангаке и случайно '
                                                      'становится его ассистенткой.',
                                              'id': 23289,
                                              'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx20668-6UslJY5NDYNh.png',
                                              'ru': 'Нодзаки-кун',
                                              'score': '7.70'}],
                        'desc': 'Искренние чувства, неловкие признания, поддержка и уютная атмосфера:',
                        'key': 'soul_romance',
                        'name': '💖 Трогательная романтика и драма',
                        'poster': 'https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101921-ufrjLzhSz7L1.jpg',
                        'shiki_genre': None,
                        'shiki_order': None,
                        'tags': '#романтика #повседневность #уют',
                        'title': 'Трогательная романтика и драма 💖'}}

def load_seen_compilation_animes(cooldown_days=7):
    """
    Loads anime IDs that were published within the cooldown period (default: 7 days).
    Anime published more than 7 days ago will naturally exit the set and become available again.
    """
    now = time.time()
    cutoff_ts = now - (cooldown_days * 86400)
    seen_ids = set()

    # 1. Local storage with timestamps
    if os.path.exists(SEEN_ANIMES_FILE):
        try:
            with open(SEEN_ANIMES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for anime_id, ts in data.items():
                        if isinstance(ts, (int, float)) and ts >= cutoff_ts:
                            seen_ids.add(str(anime_id))
                elif isinstance(data, list):
                    seen_ids.update(str(x) for x in data)
        except Exception as e:
            print(f"[Compilations] Ошибка чтения {SEEN_ANIMES_FILE}: {e}")

    # 2. Supabase Cloud Sync (items published in last 7 days)
    try:
        remote_seen = load_seen_from_supabase(category='compilation_anime', days=cooldown_days)
        seen_ids.update(str(s) for s in remote_seen)
    except Exception:
        pass

    return seen_ids

def save_seen_compilation_animes(new_anime_ids):
    """
    Saves published anime IDs with the current timestamp into both local JSON
    and Supabase cloud table with category='compilation_anime'.
    """
    now = time.time()
    cutoff_30d = now - (30 * 86400)
    data = {}

    if os.path.exists(SEEN_ANIMES_FILE):
        try:
            with open(SEEN_ANIMES_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = {k: v for k, v in loaded.items() if isinstance(v, (int, float)) and v >= cutoff_30d}
                elif isinstance(loaded, list):
                    data = {str(k): now for k in loaded}
        except Exception:
            pass

    for aid in new_anime_ids:
        data[str(aid)] = now

    try:
        with open(SEEN_ANIMES_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Compilations] Ошибка сохранения {SEEN_ANIMES_FILE}: {e}")

    try:
        save_seen_to_supabase(list(new_anime_ids), category='compilation_anime')
    except Exception:
        pass

def load_last_compilation_time():
    if os.path.exists(LAST_COMPILATION_FILE):
        try:
            with open(LAST_COMPILATION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return float(data.get('timestamp', 0))
        except Exception:
            pass
    return 0

def save_last_compilation_time(ts=None):
    if ts is None:
        ts = time.time()
    try:
        with open(LAST_COMPILATION_FILE, 'w', encoding='utf-8') as f:
            json.dump({"timestamp": ts, "formatted": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}, f, indent=2)
    except Exception:
        pass

def download_image(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'AnimeVistBot/1.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return Image.open(io.BytesIO(resp.read()))

def _get_font(size, bold=True):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_vector_star(draw, cx, cy, r_outer=7.2, r_inner=3.4, color=(251, 191, 36, 255)):
    """Draws a crisp anti-aliased 5-point star polygon."""
    points = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = r_outer if i % 2 == 0 else r_inner
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color)

def create_light_colorful_background(width, height):
    """
    Creates a beautiful, soft, light pastel gradient background:
    Soft periwinkle lilac -> soft wisteria -> delicate blush pink -> warm soft peach -> airy sky cyan
    with gentle luminous ambient orbs.
    """
    base = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(base)
    stops = [
        (199, 210, 254),  # #c7d2fe (soft celestial periwinkle)
        (221, 214, 254),  # #ddd6fe (soft wisteria lilac)
        (251, 207, 232),  # #fbcfe8 (delicate blush pink)
        (254, 215, 170),  # #fed7aa (warm soft peach)
        (186, 230, 253)   # #bae6fd (airy sky cyan)
    ]
    for y in range(height):
        for x in range(0, width, 4):
            factor = (x * 0.45 + y * 0.55) / (width * 0.45 + height * 0.55)
            seg = factor * 4.0
            idx = min(int(seg), 3)
            f = seg - idx
            cA = stops[idx]
            cB = stops[idx + 1]
            r = int(cA[0] + (cB[0] - cA[0]) * f)
            g = int(cA[1] + (cB[1] - cA[1]) * f)
            b = int(cA[2] + (cB[2] - cA[2]) * f)
            draw.rectangle([x, y, x + 3, y], fill=(r, g, b, 255))

    # Gentle luminous ambient orbs
    orbs = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_o = ImageDraw.Draw(orbs)
    draw_o.ellipse((width - 320, -60, width + 120, 380), fill=(186, 230, 253, 110))
    draw_o.ellipse((-80, height - 380, 380, height + 80), fill=(251, 207, 232, 100))
    draw_o.ellipse((width // 2 - 180, height // 2 - 180, width // 2 + 180, height // 2 + 180), fill=(254, 240, 138, 70))
    orbs = orbs.filter(ImageFilter.GaussianBlur(65))
    base = Image.alpha_composite(base, orbs)

    return base

def create_compilation_collage(items_or_urls, title_text, output_filename="compilation_collage.jpg"):
    """
    Downloads poster images and composites them into a single high-resolution,
    aesthetically polished collage banner in 2+1, 2+2, or 3+2 grid layouts
    on a luminous light colorful aurora background without header bar.
    """
    os.makedirs(COLLAGE_DIR, exist_ok=True)
    out_path = os.path.join(COLLAGE_DIR, output_filename)

    # Normalize items
    normalized_items = []
    for elem in items_or_urls:
        if isinstance(elem, dict):
            normalized_items.append(elem)
        else:
            normalized_items.append({"poster": str(elem), "ru": "", "score": ""})

    images_and_items = []
    for it in normalized_items:
        u = it.get('poster', '')
        if not u:
            continue
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'AnimeVistBot/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                img = Image.open(io.BytesIO(resp.read())).convert("RGBA")
                images_and_items.append((img, it))
        except Exception as e:
            print(f"[Compilations] Ошибка загрузки постера {u}: {e}")

    if not images_and_items:
        return None

    n = len(images_and_items)

    # 2+1, 2+2, 3+2 layout configuration
    if n == 3:
        row1_count = 2
        row2_count = 1
        cols = 2
        card_w = 440
        card_h = 620
        gap = 24
    elif n == 4:
        row1_count = 2
        row2_count = 2
        cols = 2
        card_w = 440
        card_h = 620
        gap = 24
    elif n == 5:
        row1_count = 3
        row2_count = 2
        cols = 3
        card_w = 380
        card_h = 535
        gap = 22
    else:
        cols = (n + 1) // 2
        row1_count = cols
        row2_count = n - cols
        card_w = 380
        card_h = 535
        gap = 22

    # Clean even outer padding (no header plate)
    pad_x = 28
    pad_y = 28

    row1_w = row1_count * card_w + (row1_count - 1) * gap
    total_w = pad_x * 2 + row1_w
    total_h = pad_y * 2 + card_h * 2 + gap

    # Coordinates
    cards_coords = []
    for i in range(row1_count):
        cards_coords.append((pad_x + i * (card_w + gap), pad_y))
    row2_w = row2_count * card_w + (row2_count - 1) * gap
    row2_start_x = pad_x + (row1_w - row2_w) // 2
    for i in range(row2_count):
        cards_coords.append((row2_start_x + i * (card_w + gap), pad_y + card_h + gap))

    # Beautiful light colorful background
    canvas = create_light_colorful_background(total_w, total_h)

    # Rounded corner mask template for posters
    scale = 2
    r = 14
    mask = Image.new("L", (card_w * scale, card_h * scale), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle((0, 0, card_w * scale, card_h * scale), radius=r * scale, fill=255)
    mask = mask.resize((card_w, card_h), Image.Resampling.LANCZOS)

    # Composite cards
    for idx, (raw_img, it) in enumerate(images_and_items, 1):
        if idx - 1 >= len(cards_coords):
            break
        pos_x, pos_y = cards_coords[idx - 1]

        # 1. Soft realistic layered drop shadow on gradient background
        shadow = Image.new("RGBA", (card_w + 24, card_h + 24), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rounded_rectangle((12, 12, card_w + 12, card_h + 12), radius=r + 2, fill=(10, 10, 20, 80))
        shadow = shadow.filter(ImageFilter.GaussianBlur(14))
        canvas.paste(shadow, (pos_x - 12, pos_y - 8), shadow)

        # 2. Resize and sharpen poster
        resized = raw_img.resize((card_w, card_h), Image.Resampling.LANCZOS).convert("RGBA")
        resized = resized.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=2))

        # 3. Picture-frame border
        border = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        b_draw = ImageDraw.Draw(border)
        b_draw.rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=r, outline=(255, 255, 255, 180), width=2)
        card_with_border = Image.alpha_composite(resized, border)

        # 4. Paste card with anti-aliased mask
        card_masked = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
        card_masked.paste(card_with_border, (0, 0), mask)
        canvas.paste(card_masked, (pos_x, pos_y), card_masked)

        # Rank tier colors
        if idx == 1:
            dot_color = (250, 204, 21, 255)      # Gold
            border_color = (250, 204, 21, 220)
            text_color = (254, 240, 138, 255)
        elif idx == 2:
            dot_color = (56, 189, 248, 255)     # Cyan
            border_color = (56, 189, 248, 220)
            text_color = (224, 242, 254, 255)
        elif idx == 3:
            dot_color = (244, 114, 182, 255)    # Rose
            border_color = (244, 114, 182, 220)
            text_color = (252, 231, 243, 255)
        else:
            dot_color = (129, 140, 248, 255)    # Indigo
            border_color = (129, 140, 248, 180)
            text_color = (241, 245, 249, 255)

        # 5. Top-Left Rank Badge [ • 01 ] with font size matching title (17px / 16px)
        font_size_title = 17 if card_w >= 400 else 16
        font_badge = _get_font(font_size_title, bold=True)
        num_str = f"{idx:02d}"

        badge_h = 36
        badge_w = 66
        b_r = 9
        badge = Image.new("RGBA", (badge_w, badge_h), (0, 0, 0, 0))
        bd_draw = ImageDraw.Draw(badge)
        bd_draw.rounded_rectangle((0, 0, badge_w - 1, badge_h - 1), radius=b_r, fill=(11, 15, 28, 235), outline=border_color, width=1)

        dot_r = 4.0
        dot_cx = 14
        dot_cy = badge_h / 2
        bd_draw.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=dot_color)

        t_bbox = bd_draw.textbbox((0, 0), num_str, font=font_badge)
        t_w = t_bbox[2] - t_bbox[0]
        t_h = t_bbox[3] - t_bbox[1]
        text_x = dot_cx + dot_r + (badge_w - (dot_cx + dot_r) - t_w) / 2
        text_y = (badge_h - t_h) / 2 - 2
        bd_draw.text((text_x, text_y), num_str, fill=text_color, font=font_badge)

        b_shadow = Image.new("RGBA", (badge_w + 6, badge_h + 6), (0, 0, 0, 0))
        bs_draw = ImageDraw.Draw(b_shadow)
        bs_draw.rounded_rectangle((3, 3, badge_w + 3, badge_h + 3), radius=b_r, fill=(0, 0, 0, 160))
        b_shadow = b_shadow.filter(ImageFilter.GaussianBlur(3))
        canvas.paste(b_shadow, (pos_x + 9, pos_y + 9), b_shadow)
        canvas.paste(badge, (pos_x + 12, pos_y + 12), badge)

        # 6. Top-Right Title & Rating Badge
        raw_ru = it.get('ru', '') or it.get('en', '')
        score_val = str(it.get('score', ''))
        if raw_ru or score_val:
            max_chars = 20 if card_w >= 400 else 17
            display_title = (raw_ru[:max_chars-2] + '..') if len(raw_ru) > max_chars else raw_ru
            score_text = score_val if score_val else '—'

            font_tr_title = _get_font(font_size_title, bold=True)
            font_tr_score = _get_font(16 if card_w >= 400 else 15, bold=True)

            dummy_draw = ImageDraw.Draw(canvas)
            t_bbox = dummy_draw.textbbox((0, 0), display_title, font=font_tr_title)
            title_w = t_bbox[2] - t_bbox[0]
            s_bbox = dummy_draw.textbbox((0, 0), score_text, font=font_tr_score)
            score_num_w = s_bbox[2] - s_bbox[0]
            star_r_out = 7.2
            star_r_in = 3.4
            star_space = 22
            score_w = score_num_w + star_space

            pad_tr_x = 13
            pad_tr_y = 8
            content_w = max(title_w, score_w)
            tr_w = content_w + pad_tr_x * 2
            tr_h = 58
            tr_r = 9

            tr_x = pos_x + card_w - 12 - tr_w
            tr_y = pos_y + 12

            tr_badge = Image.new("RGBA", (tr_w, tr_h), (0, 0, 0, 0))
            tr_draw = ImageDraw.Draw(tr_badge)
            tr_draw.rounded_rectangle((0, 0, tr_w - 1, tr_h - 1), radius=tr_r, fill=(11, 15, 28, 235), outline=border_color, width=1)

            # Title (right-aligned in badge)
            tr_draw.text((tr_w - pad_tr_x - title_w, pad_tr_y), display_title, fill=(255, 255, 255, 255), font=font_tr_title)

            # Vector Star + Rating (right-aligned in badge)
            score_num_x = tr_w - pad_tr_x - score_num_w
            star_cx = score_num_x - 12
            star_cy = pad_tr_y + 32
            draw_vector_star(tr_draw, star_cx, star_cy, r_outer=star_r_out, r_inner=star_r_in, color=(251, 191, 36, 255))
            tr_draw.text((score_num_x, pad_tr_y + 24), score_text, fill=(251, 191, 36, 255), font=font_tr_score)

            tr_shadow = Image.new("RGBA", (tr_w + 6, tr_h + 6), (0, 0, 0, 0))
            trs_draw = ImageDraw.Draw(tr_shadow)
            trs_draw.rounded_rectangle((3, 3, tr_w + 3, tr_h + 3), radius=tr_r, fill=(0, 0, 0, 160))
            tr_shadow = tr_shadow.filter(ImageFilter.GaussianBlur(3))
            canvas.paste(tr_shadow, (tr_x - 3, tr_y - 3), tr_shadow)
            canvas.paste(tr_badge, (tr_x, tr_y), tr_badge)

    final_rgb = canvas.convert("RGB")
    final_rgb.save(out_path, "JPEG", quality=98, subsampling=0)
    print(f"[Compilations] Высококачественный HD-коллаж успешно сгенерирован ({n} постеров): {out_path}")
    return out_path

_shikimori_cache = {}

def fetch_shikimori_candidates(genre_id=None, order="ranked", limit=20):
    """
    Queries Shikimori API dynamically to discover additional titles with in-memory caching.
    """
    cache_key = f"{genre_id}:{order}:{limit}"
    if cache_key in _shikimori_cache:
        return _shikimori_cache[cache_key]

    params = [f"order={order}", f"limit={limit}"]
    if genre_id:
        params.append(f"genre={genre_id}")
    url = f"https://shikimori.one/api/animes?{'&'.join(params)}"
    req = urllib.request.Request(url, headers={'User-Agent': 'AnimeVistBot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = []
            for a in data:
                img_path = a.get('image', {}).get('original', '')
                if not img_path or 'missing' in img_path:
                    continue
                results.append({
                    "id": a.get('id'),
                    "ru": a.get('russian') or a.get('name'),
                    "en": a.get('name'),
                    "score": a.get('score', '—'),
                    "genres": "Аниме, Приключения",
                    "poster": f"https://shikimori.one{img_path}",
                    "hook": "Захватывающий сюжет с высоким рейтингом зрителей."
                })
            _shikimori_cache[cache_key] = results
            return results
    except Exception as e:
        print(f"[Compilations] Shikimori query error: {e}")
        return []

def select_unseen_anime(theme_key, count=4, refresh=False, cooldown_days=7):
    """
    Selects N unseen anime for the compilation, strictly skipping any anime
    published within the last 7 days (cooldown_days=7).
    """
    theme = THEMES.get(theme_key, THEMES['must_watch'])
    recently_published = load_seen_compilation_animes(cooldown_days=cooldown_days)

    pool = list(theme.get('candidates', []))

    # Filter out any anime published within the last 7 days
    available = [c for c in pool if str(c['id']) not in recently_published]
    random.shuffle(available)

    # If pool is exhausted due to high frequency, fall back to recycling oldest
    if len(available) < count:
        print(f"[Compilations] Доступно {len(available)} тайтлов вне 7-дневного кулдауна (запрошено {count}), подключаем ротацию.")
        already_ids = set(c['id'] for c in available)
        remainder_pool = [c for c in pool if c['id'] not in already_ids]
        random.shuffle(remainder_pool)
        available.extend(remainder_pool)

    selected = available[:count]
    return selected

def build_compilation_content(theme_key, count=4, refresh=False):
    theme = THEMES.get(theme_key, THEMES['must_watch'])
    config = load_config()
    app_name = config.get('app', {}).get('name', 'AnimeVist')

    items = select_unseen_anime(theme_key, count=count, refresh=refresh)
    if not items:
        return None, None, None, None

    n = len(items)
    lines = [f"🌟 <b>ТОП-{n}: {theme['title']}</b>\n"]
    if n <= 5 and theme.get('desc'):
        lines.append(f"<i>{theme['desc']}</i>\n")

    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    poster_urls = []

    if n <= 5:
        # Full detailed format for 3-5 anime
        for idx, it in enumerate(items):
            em = emojis[idx] if idx < len(emojis) else f"{idx+1}."
            lines.append(f"{em} <b>«{it['ru']}»</b> / <i>{it['en']}</i>")
            lines.append(f"⭐️ <b>{it['score']}</b> | 🎭 {it['genres']}")
            lines.append(f"📝 {it['hook']}\n")
            poster_urls.append(it['poster'])
    else:
        # High-density compact format for 6-10 anime (guarantees fitting strictly in Telegram 1024-char limit)
        for idx, it in enumerate(items):
            em = emojis[idx] if idx < len(emojis) else f"{idx+1}."
            hook_short = it['hook']
            max_hook_len = 24 if n >= 9 else (36 if n >= 7 else 60)
            if len(hook_short) > max_hook_len:
                hook_short = hook_short[:max_hook_len - 2].rstrip() + '..'
            lines.append(f"{em} <b>«{it['ru']}»</b> (⭐️ {it['score']}) — {hook_short}")
            poster_urls.append(it['poster'])
        lines.append("")

    lines.append(f"✨ <i>Смотрите эти тайтлы в приложении {app_name}!</i>")
    lines.append(f"#подборка #топ_аниме {theme['tags']} #чтопосмотреть #{app_name.lower()}")

    caption = "\n".join(lines)
    if len(caption) > 1020 and n <= 5:
        trim_lines = [f"🌟 <b>ТОП-{n}: {theme['title']}</b>\n"]
        for idx, it in enumerate(items):
            em = emojis[idx] if idx < len(emojis) else f"{idx+1}."
            hk = it.get('hook', '')
            if len(hk) > 75:
                hk = hk[:73].rstrip() + '..'
            trim_lines.append(f"{em} <b>«{it['ru']}»</b> / <i>{it['en']}</i>")
            trim_lines.append(f"⭐️ <b>{it['score']}</b> | 🎭 {it['genres']}")
            trim_lines.append(f"📝 {hk}\n")
        trim_lines.append(f"✨ <i>Смотрите эти тайтлы в приложении {app_name}!</i>")
        trim_lines.append(f"#подборка #топ_аниме {theme['tags']} #чтопосмотреть #{app_name.lower()}")
        caption = "\n".join(trim_lines)

    reply_markup = None
    show_chat = config.get('announcer', {}).get('show_chat_button', False)
    chat_url = config.get('app', {}).get('chat_invite_url', '').strip()
    if show_chat and chat_url and chat_url.startswith('http'):
        reply_markup = {
            "inline_keyboard": [
                [{"text": "💬 Обсудить подборку в чате", "url": chat_url}]
            ]
        }

    return caption, poster_urls, reply_markup, items

def get_compilation_preview(theme_key=None, count=4, refresh=True):
    """
    Returns structured preview data for web dashboard and client console.
    """
    if not theme_key or theme_key == 'auto' or theme_key not in THEMES:
        theme_key = 'must_watch'

    try:
        count = max(3, min(5, int(count)))
    except (ValueError, TypeError):
        count = 4

    theme = THEMES[theme_key]
    caption, poster_urls, reply_markup, items = build_compilation_content(theme_key, count=count, refresh=refresh)

    caption_html = caption.replace('\n', '<br>') if caption else ""
    return {
        "ok": True,
        "theme": theme_key,
        "title": theme['name'],
        "desc": theme['desc'],
        "tags": theme['tags'],
        "count": len(items) if items else count,
        "items": items or [],
        "caption": caption,
        "caption_html": caption_html,
        "poster": poster_urls[0] if poster_urls else "",
        "poster_urls": poster_urls or []
    }

def run_compilation_post(genre_key=None, count=4, dry_run=False):
    sender = TelegramSender()
    try:
        count = max(3, min(5, int(count)))
    except (ValueError, TypeError):
        count = 4

    # Auto-pick next theme if not specified
    if not genre_key or genre_key == 'auto' or genre_key not in THEMES:
        keys = list(THEMES.keys())
        idx = int(time.time() / 3600) % len(keys)
        genre_key = keys[idx]

    theme = THEMES[genre_key]
    caption, poster_urls, reply_markup, chosen_items = build_compilation_content(genre_key, count=count, refresh=True)

    if not chosen_items:
        print("[Compilations] Ошибка формирования подборки (нет тайтлов).")
        return {"ok": False, "error": "No titles available"}

    # Generate combined collage poster
    clean_title = theme['title'].replace('🌟', '').replace('🏆', '').replace('🧠', '').replace('⚔️', '').replace('💖', '').replace('😂', '').replace('🌀', '').replace('💎', '').replace('🌆', '').strip()
    collage_path = create_compilation_collage(chosen_items, f"ТОП-{len(chosen_items)}: {clean_title}")

    poster_to_send = collage_path if (collage_path and os.path.exists(collage_path)) else poster_urls[0]

    if dry_run:
        print("\n[DRY-RUN] Preview Compilation:")
        print(caption)
        print(f"Caption length: {len(caption)} / 1024")
        print(f"Collage Image: {poster_to_send}")
        print(f"Included {len(chosen_items)} anime: {[c['ru'] for c in chosen_items]}")
        return {"ok": True, "theme": genre_key, "count": len(chosen_items), "caption_length": len(caption), "dry_run": True}

    res = sender.send_photo(poster_to_send, caption=caption, reply_markup=reply_markup)
    if res.get('ok'):
        print(f"[Compilations] ✅ Успешно опубликована подборка: {theme['name']} ({len(chosen_items)} аниме)")
        # Save newly published anime IDs with current timestamp to enforce 7-day cooldown
        save_seen_compilation_animes([str(it['id']) for it in chosen_items])
        save_last_compilation_time()
        return {"ok": True, "theme": genre_key, "count": len(chosen_items), "message": f"Опубликовано: {theme['name']}"}
    else:
        err = res.get('description', 'Unknown error')
        print(f"[Compilations] ❌ Ошибка публикации: {err}")
        return {"ok": False, "theme": genre_key, "error": err}

def list_available_themes():
    return [{"key": k, "name": v["name"]} for k, v in THEMES.items()]

def should_run_auto_compilation():
    config = load_config()
    ann = config.get('announcer', {})
    if not ann.get('enable_compilations', True):
        return False
    hours = float(ann.get('compilations_interval_hours', 12))
    last = load_last_compilation_time()
    return (time.time() - last) >= (hours * 3600)

if __name__ == '__main__':
    if '--auto-if-due' in sys.argv:
        if not should_run_auto_compilation():
            print("[Compilations] Интервал между подборками ещё не истёк. Пропуск.")
            sys.exit(0)

    genre = None
    count = 4
    dry = '--dry-run' in sys.argv
    for arg in sys.argv:
        if arg.startswith('--genre='):
            genre = arg.split('=', 1)[1]
        elif arg.startswith('--count='):
            try:
                count = max(3, min(5, int(arg.split('=', 1)[1])))
            except ValueError:
                pass
        elif arg in THEMES:
            genre = arg
    run_compilation_post(genre_key=genre, count=count, dry_run=dry)
