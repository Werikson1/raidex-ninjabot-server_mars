from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print("Navegando para OGameX...")
    page.goto('https://cypher.ogamex.net/')
    page.wait_for_load_state('networkidle')
    
    # Check for bot detection
    detection = page.evaluate('''({
        webdriver: navigator.webdriver,
        plugins: navigator.plugins.length,
        languages: navigator.languages.join(', '),
        platform: navigator.platform,
        userAgent: navigator.userAgent.substring(0, 80),
        hardwareConcurrency: navigator.hardwareConcurrency,
        deviceMemory: navigator.deviceMemory || 'N/A'
    })''')
    
    # Get all script sources
    scripts = page.evaluate('''
        Array.from(document.scripts).map(s => s.src || 'inline')
    ''')
    
    print("\n" + "="*70)
    print("RELATÓRIO DE DETECÇÃO DE BOT - OGAMEX")
    print("="*70)
    
    print("\n🔍 INDICADORES DE AUTOMAÇÃO:")
    print(f"   Navigator.webdriver: {detection['webdriver']} {'❌ DETECTÁVEL!' if detection['webdriver'] else '✅ OK'}")
    print(f"   Plugins instalados: {detection['plugins']} {'⚠️  Suspeito (bots têm 0)' if detection['plugins'] == 0 else '✅ OK'}")
    print(f"   Platform: {detection['platform']}")
    print(f"   User-Agent: {detection['userAgent']}...")
    
    print(f"\n📜 SCRIPTS CARREGADOS ({len(scripts)} total):")
    
    # Categorize scripts
    tracking_scripts = []
    game_scripts = []
    inline_scripts = 0
    
    for script in scripts:
        if script == 'inline':
            inline_scripts += 1
        elif any(word in script.lower() for word in ['google', 'analytics', 'tag', 'gtm']):
            tracking_scripts.append(script)
        else:
            game_scripts.append(script)
    
    print(f"\n   🎮 Scripts do Jogo: {len(game_scripts)}")
    for s in game_scripts[:5]:
        print(f"      - {s}")
    
    print(f"\n   📊 Scripts de Tracking: {len(tracking_scripts)}")
    for s in tracking_scripts:
        print(f"      - {s}")
    
    print(f"\n   📝 Scripts Inline: {inline_scripts}")
    
    # Check for specific anti-bot libraries
    print(f"\n🛡️  VERIFICANDO BIBLIOTECAS ANTI-BOT:")
    
    checks = {
        'Google reCAPTCHA': page.locator('script[src*="recaptcha"]').count(),
        'Cloudflare': page.locator('script[src*="cloudflare"]').count(),
        'FingerprintJS': page.locator('script[src*="fingerprint"]').count(),
        'DataDome': page.locator('script[src*="datadome"]').count(),
    }
    
    for name, count in checks.items():
        status = '❌ DETECTADO!' if count > 0 else '✅ Não encontrado'
        print(f"   {name}: {status}")
    
    print("\n" + "="*70)
    print("CONCLUSÃO:")
    print("="*70)
    
    if detection['webdriver']:
        print("⚠️  O site PODE detectar que você está usando automação!")
        print("    navigator.webdriver = True expõe que é um bot.")
    
    if detection['plugins'] == 0:
        print("⚠️  Navegadores reais geralmente têm plugins. 0 plugins é suspeito.")
    
    if tracking_scripts:
        print(f"⚠️  {len(tracking_scripts)} script(s) de tracking encontrados (Google Analytics).")
        print("    Eles podem coletar dados de comportamento.")
    
    if not any(checks.values()):
        print("✅ BOA NOTÍCIA: Nenhuma biblioteca anti-bot conhecida detectada!")
        print("   O OGameX parece não ter proteção avançada contra bots.")
    
    print("\n💡 RECOMENDAÇÕES:")
    print("   1. Use delays aleatórios (você já faz isso ✅)")
    print("   2. Evite padrões repetitivos muito rígidos")
    print("   3. Considere modo não-headless quando possível")
    print("   4. Mantenha sessão persistente (cookies)")
    
    browser.close()
