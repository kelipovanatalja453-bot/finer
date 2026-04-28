const { chromium } = require('playwright');
const path = require('path');

const BASE_URL = 'http://localhost:3000';
const SCREENSHOT_DIR = '/Users/zhouhongyuan/Desktop/finer/docs/screenshots/verification';

// 等待函数
const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function main() {
  console.log('🚀 启动浏览器验证...');

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: 'zh-CN'
  });
  const page = await context.newPage();

  const results = [];

  // ============================================
  // 1. 首页验证
  // ============================================
  try {
    console.log('📸 验证首页...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 });
    await wait(2000); // 等待 React 水合

    // 检查关键元素
    const title = await page.title();
    const hasContent = await page.locator('body').isVisible();

    // 截图
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '01-homepage.png'),
      fullPage: true
    });

    results.push({
      page: '首页',
      status: '✅ 通过',
      details: `标题: ${title}, 内容可见: ${hasContent}`
    });
  } catch (e) {
    results.push({ page: '首页', status: '❌ 失败', details: e.message });
  }

  // ============================================
  // 2. KOL 列表页验证
  // ============================================
  try {
    console.log('📸 验证 KOL 列表页...');
    await page.goto(`${BASE_URL}/kol`, { waitUntil: 'networkidle', timeout: 30000 });
    await wait(2000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '02-kol-list.png'),
      fullPage: true
    });

    const url = page.url();
    results.push({
      page: 'KOL 列表页',
      status: '✅ 通过',
      details: `URL: ${url}`
    });
  } catch (e) {
    results.push({ page: 'KOL 列表页', status: '❌ 失败', details: e.message });
  }

  // ============================================
  // 3. KOL 详情页验证
  // ============================================
  try {
    console.log('📸 验证 KOL 详情页...');
    // 使用一个示例 KOL ID
    await page.goto(`${BASE_URL}/kol/analyst-001`, { waitUntil: 'networkidle', timeout: 30000 });
    await wait(2000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '03-kol-detail.png'),
      fullPage: true
    });

    results.push({
      page: 'KOL 详情页',
      status: '✅ 通过',
      details: '页面加载成功'
    });
  } catch (e) {
    results.push({ page: 'KOL 详情页', status: '❌ 失败', details: e.message });
  }

  // ============================================
  // 4. KOL 对比页验证
  // ============================================
  try {
    console.log('📸 验证 KOL 对比页...');
    await page.goto(`${BASE_URL}/kol/compare`, { waitUntil: 'networkidle', timeout: 30000 });
    await wait(2000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '04-kol-compare.png'),
      fullPage: true
    });

    results.push({
      page: 'KOL 对比页',
      status: '✅ 通过',
      details: '页面加载成功'
    });
  } catch (e) {
    results.push({ page: 'KOL 对比页', status: '❌ 失败', details: e.message });
  }

  // ============================================
  // 5. 回测管理页验证
  // ============================================
  try {
    console.log('📸 验证回测管理页...');
    await page.goto(`${BASE_URL}/backtest`, { waitUntil: 'networkidle', timeout: 30000 });
    await wait(2000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '05-backtest.png'),
      fullPage: true
    });

    results.push({
      page: '回测管理页',
      status: '✅ 通过',
      details: '页面加载成功'
    });
  } catch (e) {
    results.push({ page: '回测管理页', status: '❌ 失败', details: e.message });
  }

  // ============================================
  // 6. 设置页验证
  // ============================================
  try {
    console.log('📸 验证设置页...');
    await page.goto(`${BASE_URL}/settings`, { waitUntil: 'networkidle', timeout: 30000 });
    await wait(2000);

    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, '06-settings.png'),
      fullPage: true
    });

    results.push({
      page: '设置页',
      status: '✅ 通过',
      details: '页面加载成功'
    });
  } catch (e) {
    results.push({ page: '设置页', status: '❌ 失败', details: e.message });
  }

  // ============================================
  // 输出结果
  // ============================================
  console.log('\n' + '='.repeat(60));
  console.log('📊 验证结果汇总');
  console.log('='.repeat(60));

  for (const r of results) {
    console.log(`${r.status} ${r.page}: ${r.details}`);
  }

  const passed = results.filter(r => r.status.includes('通过')).length;
  const failed = results.filter(r => r.status.includes('失败')).length;

  console.log('\n' + '='.repeat(60));
  console.log(`总计: ${results.length} 个页面, ✅ 通过: ${passed}, ❌ 失败: ${failed}`);
  console.log('='.repeat(60));

  await browser.close();
  console.log('\n🎉 验证完成！');
}

main().catch(e => {
  console.error('❌ 错误:', e.message);
  process.exit(1);
});
