const{chromium}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const evidenceDir=process.env.EVIDENCE_DIR||'/tmp/reflex-customization-pointer-evidence';
fs.mkdirSync(evidenceDir,{recursive:true});
(async()=>{
 const b=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox','--enable-unsafe-swiftshader']});
 const p=await b.newPage({viewport:{width:1366,height:1000}}),checks=[],errors=[];
 p.on('pageerror',e=>errors.push(e.message));
 const check=(name,condition)=>{assert.ok(condition,name);checks.push(name);console.log(name)};
 const calls=async()=>Number(await p.locator('#engine-calls').textContent());
 const prefs=async()=>JSON.parse(await p.locator('#preferences').textContent());
 const waitCalls=async n=>p.waitForFunction(n=>Number(document.querySelector('#engine-calls').textContent)>n,n);
 const action=async name=>{const n=await calls();await p.getByRole('button',{name,exact:true}).click();await waitCalls(n)};
 async function start(grip){await grip.scrollIntoViewIfNeeded();const r=await grip.boundingBox();await p.mouse.move(r.x+r.width/2,r.y+r.height/2);await p.mouse.down();await p.mouse.move(r.x+20,r.y-14,{steps:3});await p.locator('.pointer-ghost').waitFor();return r}
 async function dropBefore(id,screenshot){await p.evaluate(()=>window.scrollTo(0,0));const dest=p.locator(`.canvas > [data-instance="${id}"]`);await dest.scrollIntoViewIfNeeded();const r=await dest.boundingBox(),canvas=await p.locator('.canvas').boundingBox();await p.mouse.move(canvas.x+canvas.width/2,r.y+5,{steps:20});if(screenshot)await p.screenshot({path:`${evidenceDir}/${screenshot}.png`,fullPage:true});const n=await calls();await p.mouse.up();await waitCalls(n);await p.locator('.pointer-ghost').waitFor({state:'detached'});}
 try{
 await p.goto(process.env.BASE_URL||'http://127.0.0.1:4202');await p.locator('.ag-row').first().waitFor();
 const initial=await prefs();await action('Customize');
 const grid=p.locator('[data-instance=accounts]');
 await grid.locator('.ag-header-cell[col-id=revenue]').click();await grid.locator('.ag-header-cell[col-id=revenue]').click();await grid.locator('[col-id=revenue][aria-sort=descending]').waitFor();
 await grid.evaluate(el=>window.__originalGrid=el);
 let n=await calls();const before=await prefs();await start(p.getByRole('button',{name:'Drag Accounts',exact:true}));
 check('ghost is same inert actual grid node',await p.evaluate(()=>document.querySelector('.pointer-ghost')===window.__originalGrid&&window.__originalGrid.inert));
 check('pointer movement has no Python stage before release',await calls()===n&&JSON.stringify(await prefs())===JSON.stringify(before));
 await dropBefore('trend','pointer-grid-ghost');
 check('drop changes actual server draft order',(await prefs()).items[0].id==='accounts');
 check('acknowledged reorder keeps actual grid and sort',await grid.evaluate(el=>el===window.__originalGrid)&&await grid.locator('.ag-header-cell[col-id=revenue]').getAttribute('aria-sort')==='descending');
 n=await calls();await start(p.getByRole('button',{name:'Drag Revenue trend',exact:true}));await p.keyboard.press('Escape');await p.mouse.up();await p.locator('.pointer-ghost').waitFor({state:'detached'});
 check('Escape cancels without a Python stage',await calls()===n);
 const resize=p.getByRole('button',{name:'Resize Revenue trend',exact:true});const r=await start(resize);await p.mouse.move(r.x+r.width/2-430,r.y+r.height/2-72,{steps:20});await p.screenshot({path:evidenceDir + '/pointer-resize-ghost.png',fullPage:true});n=await calls();await p.mouse.up();await waitCalls(n);await p.locator('.pointer-ghost').waitFor({state:'detached'});
 const sized=(await prefs()).items.find(x=>x.id==='trend');check('resize validates snapped width and height on Python Draft',sized.width===6&&sized.height===3);
 await p.getByRole('button',{name:'Add widgets',exact:true}).click();await p.locator('.catalog').waitFor();
 const previewGrid=p.locator('[data-catalog-widget=accounts]');await previewGrid.locator('.ag-row').first().waitFor();await previewGrid.locator('.ag-header-cell[col-id=revenue]').click();await previewGrid.locator('.ag-header-cell[col-id=revenue]').click();await previewGrid.locator('[col-id=revenue][aria-sort=descending]').waitFor();
 await previewGrid.evaluate(el=>window.__catalogGrid=el);n=await calls();await start(previewGrid.locator('[data-pointer-action=add]'));
 check('drag-add ghost is same actual catalog grid',await p.evaluate(()=>document.querySelector('.pointer-ghost')===window.__catalogGrid));
 await dropBefore('search','pointer-add-grid-ghost');
 const addedGrid=p.locator('[data-instance=accounts-1]');await addedGrid.locator('[col-id=revenue][aria-sort=descending]').waitFor();
 check('catalog grid sort survives into new actual destination',await addedGrid.locator('.ag-root').count()===1);
 const previewTrend=p.locator('[data-catalog-widget=trend]');await previewTrend.locator('canvas').first().waitFor();
 await previewTrend.evaluate(el=>{const n=[...el.querySelectorAll('.xy')].find(x=>x.xy);window.__catalogChart=n;n.xy.applyState({ranges:{x:[3,9],y:[15,30]}},{history:false,animate:false})});
 const view=await previewTrend.evaluate(el=>[...el.querySelectorAll('.xy')].find(x=>x.xy).xy.state().ranges);
 await start(previewTrend.locator('[data-pointer-action=add]'));
 check('XY ghost retains actual renderer and zoomed state',await p.evaluate(()=>{const g=document.querySelector('.pointer-ghost');return g.contains(window.__catalogChart)&&window.__catalogChart.xy.state().ranges.x[0]===3}));
 await dropBefore('search','pointer-add-xy-ghost');
 await p.waitForFunction(expected=>{const n=document.querySelector('[data-instance="trend-1"] .xy');return n?.xy&&JSON.stringify(n.xy.state().ranges)===JSON.stringify(expected)},view);
 check('catalog XY zoom survives into new actual destination',await p.locator('[data-instance=trend-1] canvas').count()>0);
 await action('Cancel');check('Cancel after repeated pointer changes restores original saved preferences',JSON.stringify(await prefs())===JSON.stringify(initial));
 await action('Customize');n=await calls();await start(p.getByRole('button',{name:'Drag Accounts',exact:true}));await p.keyboard.press('Escape');await p.mouse.up();check('second canceled drag stages nothing',await calls()===n);await action('Save my session layout');check('Save after canceled drag preserves authoritative layout',JSON.stringify(await prefs())===JSON.stringify(initial));
 await action('Customize');await action('Left nav');await p.setViewportSize({width:1024,height:900});await p.getByRole('button',{name:'Add widgets',exact:true}).click();await p.locator('.catalog').waitFor();
 const laptop=await p.evaluate(()=>({canvas:document.querySelector('.canvas').getBoundingClientRect().width,dock:document.querySelector('.catalog').getBoundingClientRect().width,overflow:document.documentElement.scrollWidth>innerWidth}));
 check('1024px left-nav dock remains readable without page overflow',!laptop.overflow&&laptop.canvas>=400);await p.screenshot({path:evidenceDir + '/pointer-laptop-left.png',fullPage:true});
 check('no uncaught browser errors',errors.length===0);fs.writeFileSync(evidenceDir + '/stateful-browser-results.json',JSON.stringify({checks,errors,laptop},null,2));
 }catch(e){await p.screenshot({path:evidenceDir + '/stateful-failure.png',fullPage:true});fs.writeFileSync(evidenceDir + '/stateful-browser-results.json',JSON.stringify({checks,errors,failure:String(e)},null,2));throw e}finally{await b.close()}
})().catch(e=>{console.error(e);process.exit(1)});
