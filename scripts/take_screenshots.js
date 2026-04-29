const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const screenshotsDir = '/Users/zhouhongyuan/Desktop/finer/docs/screenshots';

// Ensure directory exists
if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir, { recursive: true });
}

async function takeScreenshots() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        viewport: { width: 1920, height: 1080 },
        deviceScaleFactor: 2,
    });
    const page = await context.newPage();

    const screenshots = [
        {
            name: 'dashboard-main.png',
            url: 'http://localhost:3000?tier=F1',
            wait: 3000,
            description: 'Dashboard 主界面 - F1 标准化台'
        },
        {
            name: 'dashboard-l0.png',
            url: 'http://localhost:3000?tier=F0',
            wait: 2000,
            description: 'F0 接入台视图'
        },
        {
            name: 'dashboard-l5.png',
            url: 'http://localhost:3000?tier=F5',
            wait: 2000,
            description: 'F5 执行台视图'
        },
        {
            name: 'integrations-hub.png',
            url: 'http://localhost:3000?tier=Integrations',
            wait: 3000,
            description: '数据源集成中心'
        },
        {
            name: 'kol-rating-demo.png',
            url: 'http://localhost:3000/demo/kol-rating',
            wait: 3000,
            description: 'KOL 评价卡片演示'
        }
    ];

    console.log('📸 开始截图...\n');

    for (const shot of screenshots) {
        try {
            console.log(`📷 截取: ${shot.description}`);
            console.log(`   URL: ${shot.url}`);

            await page.goto(shot.url, { waitUntil: 'networkidle', timeout: 30000 });
            await page.waitForTimeout(shot.wait);

            const filePath = path.join(screenshotsDir, shot.name);
            await page.screenshot({
                path: filePath,
                fullPage: false
            });

            console.log(`   ✅ 已保存: ${filePath}\n`);
        } catch (error) {
            console.log(`   ❌ 失败: ${error.message}\n`);
        }
    }

    // 截取侧边栏导航
    try {
        console.log('📷 截取: 侧边栏导航');
        await page.goto('http://localhost:3000?tier=F1', { waitUntil: 'networkidle' });
        await page.waitForTimeout(2000);

        // 截取侧边栏区域
        const sidebar = await page.locator('nav').first();
        if (await sidebar.isVisible()) {
            await sidebar.screenshot({
                path: path.join(screenshotsDir, 'sidebar-navigation.png')
            });
            console.log('   ✅ 已保存: sidebar-navigation.png\n');
        }
    } catch (error) {
        console.log(`   ❌ 失败: ${error.message}\n`);
    }

    await browser.close();
    console.log('✨ 截图完成！');
}

takeScreenshots().catch(console.error);
