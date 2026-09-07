// Скрипт для оптимизации UID дашборда
// Добавляет адаптивность для мобильных устройств и улучшает UX

const fs = require('fs');
const path = require('path');

const indexPath = path.join(__dirname, 'index.html');
let content = fs.readFileSync(indexPath, 'utf8');

// 1. Добавляем адаптивный viewport для мобильных
if (!content.includes('maximum-scale=1.0')) {
    content = content.replace(
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">'
    );
}

// 2. Добавляем адаптивные медиа-запросы перед закрывающим тегом </style>
const mobileStyles = `
    /* Мобильная адаптация */
    @media (max-width: 768px) {
        body {
            font-size: 13px;
            padding: 0;
        }
        
        header {
            padding: 0.75rem 1rem;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .header-left { flex: 1; min-width: 200px; }
        .header-center { flex: 1; justify-content: center; min-width: 200px; }
        .header-right { flex: 0; }
        
        .nav-tabs {
            padding: 0 0.75rem;
            flex-wrap: wrap;
            gap: 4px;
        }
        
        .tab-btn {
            padding: 10px 12px;
            font-size: 0.82rem;
            white-space: nowrap;
        }
        
        .app-body {
            padding: 0.75rem;
        }
        
        .grid-kpi {
            grid-template-columns: repeat(auto-fit, minmax(100%, 1fr));
            gap: 0.75rem;
        }
        
        .kpi-card {
            padding: 1rem;
        }
        
        .kpi-card h3 {
            font-size: 0.85rem;
        }
        
        .kpi-card .kpi-value {
            font-size: 1.5rem;
        }
        
        .kpi-card .kpi-label {
            font-size: 0.7rem;
        }
        
        .grid-layout {
            grid-template-columns: 1fr !important;
        }
        
        .card-grid {
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)) !important;
        }
        
        .btn {
            padding: 8px 14px;
            min-height: 38px;
            font-size: 0.82rem;
        }
        
        .btn-block {
            font-size: 0.8rem;
        }
        
        .form-group {
            gap: 0.5rem;
        }
        
        .form-group input, .form-group select {
            padding: 8px 12px;
            font-size: 0.85rem;
        }
        
        .form-group label {
            font-size: 0.75rem;
        }
        
        .card {
            padding: 1rem;
        }
        
        .card h3 {
            font-size: 0.95rem;
            margin-bottom: 0.5rem;
        }
        
        .card .card-body {
            font-size: 0.8rem;
        }
        
        .terminal {
            font-size: 0.75rem;
            padding: 1rem;
        }
        
        .tab-content {
            padding: 0;
        }
        
        .grid-2 {
            grid-template-columns: 1fr !important;
        }
        
        .grid-3 {
            grid-template-columns: repeat(2, 1fr) !important;
        }
    }
    
    /* Дополнительные улучшения для мобильных */
    @media (max-width: 480px) {
        body {
            font-size: 12px;
        }
        
        .logo-badge {
            width: 32px;
            height: 32px;
            font-size: 0.9rem;
        }
        
        .brand-title {
            font-size: 0.95rem;
        }
        
        .status-pill {
            padding: 4px 10px;
            font-size: 0.72rem;
        }
        
        .kpi-value {
            font-size: 1.3rem;
        }
        
        .btn {
            min-height: 36px;
        }
        
        .grid-kpi {
            gap: 0.5rem;
        }
    }
`;

// Вставляем стили перед </style>
if (!content.includes('/* Мобильная адаптация */')) {
    content = content.replace('</style>', `${mobileStyles}</style>`);
}

// 3. ��обавляем улучшенный класс для адаптивной сетки
if (!content.includes('.mobile-full-width')) {
    content = content.replace(
        '.grid-kpi {',
        '.mobile-full-width { width: 100% !important; max-width: none !important; }\n\n.grid-kpi {'
    );
}

fs.writeFileSync(indexPath, content, 'utf8');
console.log('✅ Дашборд оптимизирован для мобильных устройств и UX');
