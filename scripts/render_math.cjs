// Pre-render accessible math so the page needs no client-side math renderer.
// npm install --prefix /tmp/ht-policy-math-renderer --ignore-scripts katex@0.19.0
// node scripts/render_math.cjs /tmp/ht-policy-math-renderer/node_modules/katex
const fs = require('node:fs');
const path = require('node:path');
const katexPath = process.argv[2];
if (!katexPath) throw new Error('Pass the path to a KaTeX 0.19.0 package.');
const katex = require(path.resolve(katexPath));
if (katex.version !== '0.19.0') throw new Error('Expected KaTeX 0.19.0.');
const root = path.resolve(__dirname, '..');

// Same per-sample objective as sections/loss_design.tex, omitting constants.
const scale = String.raw`\textcolor{#2b65ad}{\sigma_\theta^2(o)}`;
const scaleTerm = String.raw`\frac{d}{2}\log ${scale}`;
const tailTerm = String.raw`\textcolor{#168452}{\frac{\nu+d}{2}\log\!\left(1+\frac{\lVert r\rVert_2^2}{\nu\,${scale}}\right)}`;
const formulas = {
  'ht-desktop': {tex: String.raw`\ell_{\mathrm{HT}}(o,a)=${scaleTerm}+${tailTerm}`, displayMode: true},
  'ht-mobile': {tex: String.raw`\begin{gathered}\ell_{\mathrm{HT}}(o,a)=${scaleTerm}\\[0.5em]+${tailTerm}\end{gathered}`, displayMode: true},
  residual: {tex: String.raw`r=f_\theta(o)-a`},
  dimension: {tex: 'd'},
  nu: {tex: String.raw`\nu`},
};

const page = path.join(root, 'index.html');
let html = fs.readFileSync(page, 'utf8');
for (const [name, {tex, displayMode = false}] of Object.entries(formulas)) {
  const pattern = new RegExp(`<!-- math:${name} -->[\\s\\S]*?<!-- /math:${name} -->`, 'g');
  if ([...html.matchAll(pattern)].length !== 1) throw new Error(`Expected one placeholder for ${name}.`);
  const rendered = katex.renderToString(tex, {displayMode, output: 'htmlAndMathml', throwOnError: true, strict: 'error', trust: false});
  html = html.replace(pattern, `<!-- math:${name} -->${rendered}<!-- /math:${name} -->`);
}
fs.writeFileSync(page, html);

const vendor = path.join(root, 'assets', 'katex');
const fonts = path.join(vendor, 'fonts');
fs.mkdirSync(fonts, {recursive: true});
let css = fs.readFileSync(path.join(katexPath, 'dist', 'katex.min.css'), 'utf8');
// Modern browsers use WOFF2; remove the unused fallback file references.
css = css.replace(/,url\([^)]*\.(?:woff|ttf)\)\s*format\([^)]*\)/g, '');
fs.writeFileSync(path.join(vendor, 'katex.min.css'), css);
for (const font of fs.readdirSync(path.join(katexPath, 'dist', 'fonts'))) {
  if (font.endsWith('.woff2')) fs.copyFileSync(path.join(katexPath, 'dist', 'fonts', font), path.join(fonts, font));
}
fs.copyFileSync(path.join(katexPath, 'LICENSE'), path.join(vendor, 'LICENSE'));
console.log(`Rendered ${Object.keys(formulas).length} formulas with KaTeX ${katex.version}.`);
