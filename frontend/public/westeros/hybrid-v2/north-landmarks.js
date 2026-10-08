const GOLD = ['#79501f', '#f4d896', '#dab36a', '#7b5425'];
export function paintFlagFrame(ctx, x, y, r, region, close) {
  const shield = (expand = 0) => {
    ctx.beginPath(); ctx.moveTo(x-r-3-expand,y-r-4-expand);
    ctx.lineTo(x+r+3+expand,y-r-4-expand); ctx.lineTo(x+r+3+expand,y+r*.6);
    ctx.quadraticCurveTo(x+r,y+r+4+expand,x,y+r+6+expand);
    ctx.quadraticCurveTo(x-r,y+r+4+expand,x-r-3-expand,y+r*.6); ctx.closePath();
  };
  ctx.save();
  const gold = ctx.createLinearGradient(x-r-4,y-r-6,x+r+4,y+r+8);
  GOLD.forEach((color,i)=>gold.addColorStop(i/3,color));
  shield(1);ctx.strokeStyle='#20160d';ctx.lineWidth=close?3:5;ctx.stroke();
  shield(1);ctx.strokeStyle=gold;ctx.lineWidth=close?1.7:2.8;ctx.stroke();
  shield(-1);ctx.strokeStyle=region;ctx.lineWidth=close?1:1.4;ctx.stroke();
  if(!close){
    ctx.fillStyle=gold;
    for(const dx of [-r-3,r+3]){ctx.beginPath();ctx.arc(x+dx,y-r-4,1.5,0,Math.PI*2);ctx.fill();}
    ctx.beginPath();ctx.moveTo(x,y-r-8);ctx.lineTo(x+2.6,y-r-5);ctx.lineTo(x,y-r-2);ctx.lineTo(x-2.6,y-r-5);ctx.closePath();ctx.fill();
  }
  ctx.restore();
}

export function wallEndpoints(rows) {
  const name = p => (p.gameName||p.sourceMap?.name||p.name||'').replace(/[\s‌_-]/g,'').toLowerCase();
  const find = names => rows.find(p=>names.includes(name(p)));
  const east=find(['ایستواچ','eastwatch','eastwatchbythesea']);
  const west=find(['شدوتاور','shadowtower']);
  const e=east?.position||{x:.4439649821,y:.0378940962,z:-1.7837928361};
  const w=west?.position||{x:.0705229546,y:.0352436419,z:-1.7307237550};
  return {east:{...e,z:e.z-.038},west:{...w,z:w.z-.038}};
}

export function createIceSurface() {
  const canvas=document.createElement('canvas');canvas.width=2048;canvas.height=1024;
  const ctx=canvas.getContext('2d'),image=ctx.createImageData(2048,1024);
  const hash=(x,y)=>{let n=Math.imul(x,374761393)+Math.imul(y,668265263);n=Math.imul(n^(n>>>13),1274126177);return ((n^(n>>>16))>>>0)/4294967295;};
  const noise=(x,y)=>{const ix=Math.floor(x),iy=Math.floor(y),fx=x-ix,fy=y-iy,s=fx*fx*(3-2*fx),t=fy*fy*(3-2*fy);return (hash(ix,iy)*(1-s)+hash(ix+1,iy)*s)*(1-t)+(hash(ix,iy+1)*(1-s)+hash(ix+1,iy+1)*s)*t;};
  for(let y=0;y<1024;y++)for(let x=0;x<2048;x++){
    const h=y/1024,bend=noise(x*.008,y*.007)*18;
    const erosion=noise((x+bend)*.065,y*.003),cloud=noise(x*.023,y*.034),fine=noise(x*.16,y*.12);
    const strata=Math.pow(Math.abs(Math.sin(y*.058+noise(x*.006,y*.008)*5)),12);
    const shade=.36+.30*h+.22*erosion+.10*cloud+.035*fine-strata*.09;
    const at=(y*2048+x)*4;
    image.data[at]=Math.min(255,185*shade+45*h*h);image.data[at+1]=Math.min(255,226*shade+32*h*h);image.data[at+2]=Math.min(255,248*shade+20*h*h);image.data[at+3]=255;
  }
  ctx.putImageData(image,0,0);
  for(let i=0;i<180;i++){
    let x=hash(i,73)*2048,y=hash(i,112)*1024;
    ctx.beginPath();ctx.moveTo(x,y);
    for(let j=0;j<7;j++){x+=(hash(i,j)-.5)*36;y+=9+hash(i+20,j)*25;ctx.lineTo(x,y);}
    ctx.strokeStyle='rgba(25,66,89,.38)';ctx.lineWidth=.7+hash(i,37)*2;ctx.stroke();
    ctx.translate(1.5,0);ctx.strokeStyle='rgba(228,249,255,.46)';ctx.lineWidth=.8;ctx.stroke();ctx.translate(-1.5,0);
  }
  ctx.fillStyle='#ffffff';ctx.fillRect(0,0,8,8);
  return canvas;
}

export function buildIceWall({east,west}, sampleHeight) {
  const packed=[],indices=[],uv=[];
  const depth=.011,height=.057,segments=128,layers=12;
  const portals=[.025,.55,.975];
  function face(a,b,c,d,color,ice=false){
    const u=b.map((v,i)=>v-a[i]),v=c.map((v,i)=>v-a[i]);
    let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],length=Math.hypot(...n)||1;
    n=n.map(v=>v/length);const offset=packed.length/10;
    for(const p of [a,b,c,d]){
      packed.push(...p,...n,...color,1);
      uv.push(...(ice?[.015+.97*(p[0]-west.x)/(east.x-west.x),.025+.94*(p[1]-.032)/.067]:[.003,.006]));
    }
    indices.push(offset,offset+1,offset+2,offset,offset+2,offset+3);
  }
  function box(x,y,z,w,h,d,col){
    face([x-w,y,z+d],[x+w,y,z+d],[x+w,y+h,z+d],[x-w,y+h,z+d],col);
    face([x+w,y,z-d],[x-w,y,z-d],[x-w,y+h,z-d],[x+w,y+h,z-d],col);
    face([x-w,y,z-d],[x-w,y,z+d],[x-w,y+h,z+d],[x-w,y+h,z-d],col);
    face([x+w,y,z+d],[x+w,y,z-d],[x+w,y+h,z-d],[x+w,y+h,z+d],col);
    face([x-w,y+h,z-d],[x-w,y+h,z+d],[x+w,y+h,z+d],[x+w,y+h,z-d],col);
  }
  const nodes=Array.from({length:segments+1},(_,i)=>{
    const t=i/segments,x=west.x+(east.x-west.x)*t;
    const z=west.z+(east.z-west.z)*t+Math.sin(t*Math.PI)*Math.sin(t*7)*.0015;
    const base=sampleHeight(x,z)?.height??.037;
    const top=west.y+(east.y-west.y)*t+height+Math.sin(t*Math.PI)*.003+Math.sin(t*103)*.00045+Math.sin(t*211)*.00025;
    return {x,z,base,top,t};
  });
  const point=(p,f,side=1)=>{
    const swell=Math.sin(p.t*49+f*2)*.0012+Math.sin(p.t*113-f*7)*.0007+Math.sin(p.t*227+f*31)*.00035;
    return [p.x,p.base+(p.top-p.base)*f,p.z+side*(depth*(1-.36*f)+swell)];
  };
  for(let i=0;i<segments;i++){
    const a=nodes[i],b=nodes[i+1];
    const gate=portals.some(t=>Math.abs((a.t+b.t)/2-t)<.009);
    for(let j=0;j<layers;j++){
      if(gate&&j<2)continue;
      const f=j/layers,g=(j+1)/layers;
      face(point(a,f),point(b,f),point(b,g),point(a,g),[.93,.98,1],true);
      face(point(b,f,-1),point(a,f,-1),point(a,g,-1),point(b,g,-1),[.93,.98,1],true);
    }
    face(point(a,1,-1),point(a,1),point(b,1),point(b,1,-1),[.93,.97,1]);
    // Local ice shelves break up the face without a continuous artificial skirt.
    if(i%7===2||i%11===4){
      const f=.18+(.5+.5*Math.sin(i*1.73))*.62;
      const c=point(a,f),d=point(b,f);
      face(c,d,[d[0],d[1]+.001,d[2]+.0005],[c[0],c[1]+.0006,c[2]+.0007],[.88,.96,1],true);
    }
  }
  for(const a of [nodes[0],nodes.at(-1)])face(point(a,0,-1),point(a,0),point(a,1),point(a,1,-1),[.92,.97,1],true);
  const timber=[.16,.13,.11],frost=[.78,.87,.90];
  for(const t of portals){
    const a=nodes[Math.round(t*segments)],front=a.z+depth+.0004,y=a.base;
    box(a.x-.0034,y,front,.0008,.011,.001,[.30,.37,.40]);
    box(a.x+.0034,y,front,.0008,.011,.001,[.30,.37,.40]);
    box(a.x,y+.010,front,.0041,.001,.001,frost);
    for(let k=-2;k<=2;k++)box(a.x+k*.001,y,front-.0012,.00018,.010,.00016,[.09,.12,.14]);
  }
  // Castle Black's enclosed lift is a slender dark shaft attached to the ice.
  const a=nodes[Math.round(.55*segments)],px=a.x+.007,pz=a.z+depth*.72+.001;
  box(px,a.base,pz,.00125,a.top-a.base+.001,.00065,[.10,.14,.16]);
  for(const dx of [-.00135,.00135])box(px+dx,a.base,pz+.0007,.00018,a.top-a.base+.002,.0002,[.28,.32,.32]);
  box(px,a.base+.009,pz+.001,.0016,.0035,.001,[.18,.20,.19]);
  box(px,a.top-.001,pz,.0017,.002,.001,[.24,.28,.28]);
  return {packed:new Float32Array(packed),indices:new Uint32Array(indices),uv:new Float32Array(uv),nodes};
}


export function enhanceLandmarkRuntime(source) {
  const marker="ctx.strokeStyle=color;ctx.lineWidth=close?2:3;ctx.stroke();";
  if(!source.includes(marker))throw Error('Flag frame integration point missing');
  source=source.replace(marker,"window.valyriaNorth.paintFlagFrame(ctx,x,y,r,color,close);");
  return source+`\n
let northWallKey='',northWallBuffers=[],northWallNodes=[],snowOverview=null,northWallTexture=null;
const northSnowTiles=new Map(),northSnowPending=new Set();
function ensureNorthWall(){
 if(!main||!center||!placementHeight)return;
 const endpoints=window.valyriaNorth.wallEndpoints(saved),key=JSON.stringify(endpoints);
 if(key===northWallKey)return;
 const mesh=window.valyriaNorth.buildIceWall(endpoints,heightAt);
 for(const b of northWallBuffers)b.vao?gl.deleteVertexArray(b.vao):gl.deleteBuffer(b.buffer);
 northWallBuffers=[];groups=groups.filter(g=>!g.northWall);
 const vao=gl.createVertexArray();gl.bindVertexArray(vao);northWallBuffers.push({vao});
 const vb=gl.createBuffer();northWallBuffers.push({buffer:vb});gl.bindBuffer(gl.ARRAY_BUFFER,vb);gl.bufferData(gl.ARRAY_BUFFER,mesh.packed,gl.STATIC_DRAW);
 for(const [loc,size,off]of [[0,3,0],[1,3,12],[2,4,24]]){gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,40,off)}
 for(const loc of [3,4,5,6])gl.disableVertexAttribArray(loc);gl.vertexAttrib1f(4,0);
 const uvBuffer=gl.createBuffer();northWallBuffers.push({buffer:uvBuffer});gl.bindBuffer(gl.ARRAY_BUFFER,uvBuffer);gl.bufferData(gl.ARRAY_BUFFER,mesh.uv,gl.STATIC_DRAW);gl.enableVertexAttribArray(3);gl.vertexAttribPointer(3,2,gl.FLOAT,false,8,0);
 if(!northWallTexture){northWallTexture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,northWallTexture);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,window.valyriaNorth.createIceSurface());gl.generateMipmap(gl.TEXTURE_2D);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR_MIPMAP_LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);}

 const ib=gl.createBuffer();northWallBuffers.push({buffer:ib});gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,mesh.indices,gl.STATIC_DRAW);
 groups.push({isCastle:true,permanentNature:true,northWall:true,vao,count:mesh.indices.length,type:gl.UNSIGNED_INT,base:[1,1,1],emission:[.20,.22,.24],texture:northWallTexture,opacity:1});
 northWallNodes=mesh.nodes;northWallKey=key;
}
function fetchNorthSnow(key,path,done){if(northSnowPending.has(key))return;northSnowPending.add(key);mapAsset(path).then(b=>createImageBitmap(new Blob([b],{type:'image/webp'}))).then(im=>{northSnowPending.delete(key);done(im);paintHybridGround()}).catch(()=>northSnowPending.delete(key))}
function paintPermanentNorthSnow(){
 if(!hybridMeta||!center)return;
 const ctx=groundCanvas.getContext('2d'),w=canvas.clientWidth,h=canvas.clientHeight,m=hybridMeta,scale=zoom*h/2,size=m.span*scale;
 const ends=window.valyriaNorth.wallEndpoints(saved),{east,west}=ends;
 const boundary=x=>{const t=Math.max(0,Math.min(1,(x-west.x)/(east.x-west.x)));return west.z+(east.z-west.z)*t;};
 const edge=[];for(let i=0;i<=64;i++){const x=-1.2+i/64*2.4;edge.push(projectEffect([x,.037,boundary(x)]));}
 ctx.save();ctx.beginPath();ctx.moveTo(-100000,-100000);ctx.lineTo(100000,-100000);for(let i=edge.length-1;i>=0;i--)ctx.lineTo(...edge[i]);ctx.closePath();ctx.clip();
 const ox=m.xmin*scale+(pan[0]+1)*w/2,oy=(1.1-pan[1])*h/2-m.ymax*scale;
 if(snowOverview)ctx.drawImage(snowOverview,ox,oy,size*m.cols,size);else fetchNorthSnow('overview','north-snow/overview.webp',im=>snowOverview=im);
 if(size*Math.min(devicePixelRatio,2)>384)for(let col=0;col<m.cols;col++){
  const x=ox+col*size;if(x>w||x+size<0||oy>h||oy+size<0)continue;
  const im=northSnowTiles.get(col);if(im)ctx.drawImage(im,x,oy,size+.4,size+.4);else fetchNorthSnow(col,'north-snow/'+col+'.webp',im=>northSnowTiles.set(col,im));
 }
 ctx.restore();
}
const preNorthGround=paintHybridGround;paintHybridGround=function(){preNorthGround();paintPermanentNorthSnow()};
const preNorthDraw=draw;draw=function(t){ensureNorthWall();preNorthDraw(t)};
`;
}
