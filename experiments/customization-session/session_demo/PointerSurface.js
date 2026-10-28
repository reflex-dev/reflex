import React, { useEffect, useRef } from "react";

export function PointerSurface({children, editing, revision, result, onCommand}) {
  const root = useRef(null), current = useRef(null), props = useRef({});
  props.current = {editing, revision, result, onCommand};
  useEffect(() => {
    const host = root.current;
    let sequence = 0;
    const say = message => { host.querySelector("[data-pointer-live]").textContent = message; };
    const clean = message => {
      const g = current.current;
      if (!g) return;
      g.source.classList.remove("pointer-ghost");
      if (g.originalStyle === null) g.source.removeAttribute("style");
      else g.source.setAttribute("style", g.originalStyle);
      g.source.inert = g.originalInert;
      if (g.originalHidden === null) g.source.removeAttribute("aria-hidden");
      else g.source.setAttribute("aria-hidden", g.originalHidden);
      g.placeholder?.remove(); g.target?.remove();
      if(g.scrollFrame)cancelAnimationFrame(g.scrollFrame);
      try { g.grip.releasePointerCapture(g.pointerId); } catch {}
      delete host.dataset.pointerActive; delete host.dataset.pointerPending;
      current.current = null;
      if (message) say(message);
    };
    host.__pointerClean = clean;
    const show = g => {
      const box = g.source.getBoundingClientRect();
      g.widthPx = box.width; g.heightPx = box.height;
      g.placeholder = document.createElement("div");
      g.placeholder.className = "pointer-placeholder";
      g.placeholder.style.cssText = `height:${box.height}px;width:${box.width}px;max-width:100%;flex-shrink:0`;
      g.placeholder.textContent = `Moving ${g.title}`;
      g.placeholder.setAttribute("aria-hidden", "true");
      g.source.before(g.placeholder);
      g.source.classList.add("pointer-ghost");
      g.source.inert = true; g.source.setAttribute("aria-hidden", "true");
      Object.assign(g.source.style, {position:"fixed",left:`${box.left}px`,top:`${box.top}px`,width:`${box.width}px`,height:`${box.height}px`,margin:"0",zIndex:"1000",pointerEvents:"none",opacity:"0.86",transformOrigin:"top left",transform:g.op === "resize" ? "none" : `scale(${Math.min(1,320/box.width)})`});
      g.target = document.createElement("div");g.target.className="pointer-drop-target";
      g.target.setAttribute("aria-hidden","true");document.body.append(g.target);
      g.active = true;host.dataset.pointerActive="true";
      if(g.op!=='resize'){
        const scroll=()=>{if(current.current!==g||g.pending)return;let delta=0;if(g.lastY>innerHeight-36)delta=14;else if(g.lastY<36)delta=-14;if(delta){window.scrollBy(0,delta);target(g,g.lastX,g.lastY);}g.scrollFrame=requestAnimationFrame(scroll);};
        g.scrollFrame=requestAnimationFrame(scroll);
      }
      say(`${g.title}. Move to the widget canvas. Escape cancels.`);
    };
    const target = (g,x,y) => {
      const canvas = host.querySelector(".canvas"), box=canvas.getBoundingClientRect();
      const valid=x>=box.left&&x<=box.right&&y>=box.top&&y<=box.bottom;
      g.valid=valid;
      g.target.style.display=valid?"block":"none";
      if (!valid) {g.before=""; return;}
      const cards=[...canvas.querySelectorAll(":scope > [data-instance]")].filter(n=>n!==g.source);
      const next=cards.find(n=>{const r=n.getBoundingClientRect();return y<r.top+r.height/2;});
      g.before=next?.dataset.instance||"";
      const lineY=next?next.getBoundingClientRect().top-9:box.bottom-8;
      Object.assign(g.target.style,{left:`${box.left+12}px`,top:`${lineY}px`,width:`${Math.max(0,box.width-24)}px`});
      g.target.textContent=`${g.op==='add'?'Add':'Move'} ${g.title} here`;
    };
    const down = event => {
      if (!props.current.editing || current.current || event.button!==0) return;
      const grip=event.target.closest("[data-pointer-action]");
      if (!grip || !host.contains(grip)) return;
      const source=grip.closest("[data-instance], [data-catalog-widget]");
      if (!source) return;
      event.preventDefault();event.stopPropagation();
      const chart=[...source.querySelectorAll(".xy")].find(n=>n.xy);
      current.current={source,grip,pointerId:event.pointerId,op:grip.dataset.pointerAction,id:source.dataset.instance||"",widget:source.dataset.catalogWidget||source.dataset.widget,title:source.querySelector("h2,h3")?.textContent||"Widget",startX:event.clientX,startY:event.clientY,revision:props.current.revision,width:Number(source.dataset.columns||12),height:Number(source.dataset.rows||4),minHeight:Number(source.dataset.minHeight||2),maxHeight:Number(source.dataset.maxHeight||8),originalStyle:source.getAttribute("style"),originalInert:source.inert,originalHidden:source.getAttribute("aria-hidden"),xyState:chart?.xy.state(),active:false,pending:false};
      try {grip.setPointerCapture(event.pointerId);} catch {}
    };
    const move = event => {
      const g=current.current;
      if (!g || g.pending || event.pointerId!==g.pointerId) return;
      if (!g.active && Math.hypot(event.clientX-g.startX,event.clientY-g.startY)<6) return;
      event.preventDefault();event.stopPropagation();
      g.lastX=event.clientX;g.lastY=event.clientY;
      if (!g.active) show(g);
      if (g.op==='resize') {
        const canvas=host.querySelector('.canvas').getBoundingClientRect();
        g.nextWidth=g.width+(event.clientX-g.startX)/canvas.width*12<9?6:12;
        g.nextHeight=Math.max(g.minHeight,Math.min(g.maxHeight,g.height+Math.round((event.clientY-g.startY)/72)));
        const width=Math.max(Math.min(canvas.width,460),canvas.width*g.nextWidth/12);
        Object.assign(g.source.style,{width:`${width}px`,height:`${Math.max(120,g.heightPx+(g.nextHeight-g.height)*72)}px`,overflow:'hidden'});
        g.placeholder.style.height=g.source.style.height;g.valid=true;g.target.style.display='none';
        say(`Resize ${g.title}: ${g.nextWidth===12?'full':'half'} width, ${g.nextHeight} height units. Escape cancels.`);
      } else {
        g.source.style.left=`${event.clientX+14}px`;g.source.style.top=`${event.clientY+14}px`;
        target(g,event.clientX,event.clientY);
      }
      if (event.clientY>innerHeight-36) window.scrollBy(0,18);
      else if(event.clientY<36) window.scrollBy(0,-18);
    };
    const up = event => {
      const g=current.current;
      if (!g || g.pending || event.pointerId!==g.pointerId) return;
      event.preventDefault();event.stopPropagation();
      if (!g.active) {clean();return;}
      if (g.op!=='resize') target(g,event.clientX,event.clientY);
      else {const box=host.querySelector('.canvas').getBoundingClientRect();g.valid=event.clientX>=box.left&&event.clientX<=box.right&&event.clientY>=box.top&&event.clientY<=box.bottom;}
      if (!g.valid) {clean('Drop canceled. Choose the widget canvas.');return;}
      if(g.op==='resize'&&g.width===g.nextWidth&&g.height===g.nextHeight){clean('Size unchanged.');return;}
      if(g.op==='move'){
        const original=[...host.querySelectorAll('.canvas > [data-instance]')].map(n=>n.dataset.instance);
        const proposed=original.filter(id=>id!==g.id);const at=g.before?proposed.indexOf(g.before):proposed.length;proposed.splice(at,0,g.id);
        if(JSON.stringify(original)===JSON.stringify(proposed)){clean('Order unchanged.');return;}
      }
      g.requestId=String(++sequence);g.pending=true;host.dataset.pointerPending='true';
      g.target.style.display='none';say('Validating the drop on the server.');
      props.current.onCommand({op:g.op,id:g.id,widget:g.widget,before:g.before||'',width:g.nextWidth||g.width,height:g.nextHeight||g.height,revision:g.revision,request_id:g.requestId});
    };
    const cancel = event => {
      const g=current.current;if(!g||g.pending)return;
      if(event.type==='keydown'&&event.key!=='Escape')return;
      if(event.type==='pointercancel'&&event.pointerId!==g.pointerId)return;
      event.preventDefault();event.stopPropagation();clean('Gesture canceled. Draft unchanged.');
    };
    host.addEventListener('pointerdown',down,true);
    document.addEventListener('pointermove',move,{capture:true,passive:false});
    document.addEventListener('pointerup',up,true);document.addEventListener('pointercancel',cancel,true);document.addEventListener('keydown',cancel,true);window.addEventListener('blur',cancel);
    return()=>{clean();delete host.__pointerClean;host.removeEventListener('pointerdown',down,true);document.removeEventListener('pointermove',move,true);document.removeEventListener('pointerup',up,true);document.removeEventListener('pointercancel',cancel,true);document.removeEventListener('keydown',cancel,true);window.removeEventListener('blur',cancel);};
  },[]);
  useEffect(()=>{
    const g=current.current;if(!g)return;
    if(!editing){root.current.__pointerClean?.('Gesture canceled. Edit mode closed.');return;}
    if(g.pending&&result?.request_id===g.requestId){
      const xyState=g.xyState, destinationId=result.id, restore=result.accepted&&g.op==='add'&&g.widget==='trend';
      root.current.__pointerClean?.(result.accepted?'Drop accepted by Python Draft.':`Drop rejected. ${result.error||'Draft unchanged.'}`);
      if(restore){let attempts=0;const apply=()=>{const card=[...root.current.querySelectorAll('.canvas > [data-instance]')].find(n=>n.dataset.instance===destinationId);const chart=card&&[...card.querySelectorAll('.xy')].find(n=>n.xy);if(chart){chart.xy.applyState(xyState,{history:false,animate:false});return;}if(++attempts<60)requestAnimationFrame(apply);};requestAnimationFrame(apply);}
    }else if(!g.pending&&revision!==g.revision){root.current.__pointerClean?.('Gesture canceled. The server draft changed.');}
  },[editing,revision,result]);
  return React.createElement('div',{ref:root,className:'pointer-surface'},children,React.createElement('span',{'data-pointer-live':'',className:'sr-only',role:'status','aria-live':'polite'}));
}
