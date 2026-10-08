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
  const canvas=document.createElement('canvas');canvas.width=1024;canvas.height=512;
  const ctx=canvas.getContext('2d'),image=ctx.createImageData(canvas.width,canvas.height);
  const fract=n=>n-Math.floor(n),hash=n=>fract(Math.sin(n*127.1+311.7)*43758.5453);
  const noise=x=>{const i=Math.floor(x),f=x-i,s=f*f*(3-2*f);return hash(i)*(1-s)+hash(i+1)*s;};
  for(let y=0;y<512;y++)for(let x=0;x<1024;x++){
    const bend=Math.sin(y*.009+x*.002)*6+Math.sin(y*.023)*2;
    const bands=noise((x+bend)*.029)*.55+noise((x+bend)*.092)*.30+noise((x+bend)*.28)*.15;
    const grain=hash(x+y*1024)-.5,cloud=noise(x*.011+y*.026);
    const frost=noise(x*.17+y*.19)*noise(x*.07-y*.13);
    const shade=.63+bands*.30+cloud*.055+grain*.028+(frost-.25)*.065;
    const at=(y*1024+x)*4;
    image.data[at]=Math.round(206*shade);image.data[at+1]=Math.round(235*shade);image.data[at+2]=Math.round(250*shade);image.data[at+3]=255;
  }
  ctx.putImageData(image,0,0);
  // Cracks branch and fade into the ice instead of repeating across each slab.
  for(let i=0;i<93;i++){
    let x=hash(i+73)*1024,y=hash(i+112)*512;
    ctx.beginPath();ctx.moveTo(x,y);
    const steps=3+Math.floor(hash(i+199)*6);
    for(let j=0;j<steps;j++){x+=(hash(i*17+j)-.5)*25;y+=13+hash(i*9+j)*24;ctx.lineTo(x,y);}
    ctx.strokeStyle='rgba(57,103,132,.34)';ctx.lineWidth=.7+hash(i+37)*1.5;ctx.stroke();
    ctx.strokeStyle='rgba(232,250,255,.32)';ctx.lineWidth=.65;ctx.translate(1.5,0);ctx.stroke();ctx.translate(-1.5,0);
  }
  ctx.fillStyle='#ffffff';ctx.fillRect(0,0,8,8);
  return canvas;
}

export function buildIceWall({east,west}, sampleHeight) {
  const packed=[],indices=[],uv=[];
  const depth=.011,height=.057,segments=96,layers=8;
  const portals=[.025,.55,.975];
  function face(a,b,c,d,color,ice=false){
    const u=b.map((v,i)=>v-a[i]),v=c.map((v,i)=>v-a[i]);
    let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],length=Math.hypot(...n)||1;
    n=n.map(v=>v/length);const offset=packed.length/10;
    for(const p of [a,b,c,d]){
      packed.push(...p,...n,...color,1);
      uv.push(...(ice?[.015+.97*(p[0]-west.x)/(east.x-west.x),.03+.94*(p[1]-.032)/.080]:[.003,.006]));
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
    const top=west.y+(east.y-west.y)*t+height+Math.sin(t*Math.PI)*.003;
    return {x,z,base,top,t};
  });
  const point=(p,f,side=1)=>{
    const swell=Math.sin(p.t*49+f*2)*.0006+Math.sin(p.t*113-f*7)*.0003;
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
    // Uneven snow shoulders soften the cliff's base and crest.
    const mound=.0015+(1+Math.sin(i*.81))*.0012;
    face([a.x,a.base-.0006,a.z+depth+.003+(Math.sin(i*.63)+1)*.0008],[b.x,b.base-.0006,b.z+depth+.003+(Math.sin((i+1)*.63)+1)*.0008],point(b,.09),point(a,.09),[.87,.94,.98]);
    const c=point(a,1),d=point(b,1);
    face([c[0],c[1]-.002,c[2]+.0018],[d[0],d[1]-.002,d[2]+.0018],[d[0],d[1]+mound*.15,d[2]],[c[0],c[1]+mound*.15,c[2]],[.97,.99,1]);
    if(i%5===2){
      const x=a.x+.0007,z=c[2]+.0017,tip=.006+(.5+.5*Math.sin(i*2.71))*.009;
      face([x-.0006,c[1]-.001,z],[x+.0006,c[1]-.001,z],[x+.00015,c[1]-tip,z+.0003],[x-.0001,c[1]-tip*.75,z],[.79,.92,.99]);
    }
  }
  for(const a of [nodes[0],nodes.at(-1)])face(point(a,0,-1),point(a,0),point(a,1),point(a,1,-1),[.92,.97,1],true);
  const timber=[.16,.13,.11],frost=[.78,.87,.90];
  // Patrol walkway with wooden rails, instead of castle-like ice battlements.
  for(let i=0;i<segments;i+=3){
    const a=nodes[i],b=nodes[Math.min(segments,i+3)],z=a.z+depth*.48;
    box(a.x,a.top+.0003,z,.00035,.0035,.0004,timber);
    face([a.x,a.top+.003,z],[b.x,b.top+.003,b.z+depth*.48],[b.x,b.top+.0036,b.z+depth*.48],[a.x,a.top+.0036,z],timber);
  }
  for(const t of portals){
    const a=nodes[Math.round(t*segments)],front=a.z+depth+.0004,y=a.base;
    // Frozen stone gate surround and iron portcullis inside the tunnel.
    box(a.x-.0034,y,front,.0008,.015,.001,[.43,.51,.53]);
    box(a.x+.0034,y,front,.0008,.015,.001,[.43,.51,.53]);
    box(a.x,y+.013,front,.0041,.0015,.001,frost);
    for(let k=-2;k<=2;k++)box(a.x+k*.001,y,front-.0012,.00018,.013,.00016,[.11,.15,.16]);
    // Three compact watch platforms and exposed timber lift towers.
    const px=a.x+.009,pz=a.z+depth+.006;
    for(const dx of [-.002,.002]){
      box(px+dx,y,pz,.00032,a.top-y+.006,.0004,timber);
      box(px+dx,a.top+.001,a.z,.0003,.010,.00035,timber);
    }
    box(px,a.top+.002,a.z,.0032,.001,.004,timber);
    const roof=a.top+.014;
    face([px-.004,roof-.002,a.z-.005],[px+.004,roof-.002,a.z-.005],[px+.004,roof,a.z],[px-.004,roof,a.z],[.22,.25,.25]);
    face([px-.004,roof,a.z],[px+.004,roof,a.z],[px+.004,roof-.002,a.z+.005],[px-.004,roof-.002,a.z+.005],[.81,.9,.94]);
    box(px,y+.006,pz,.0022,.0025,.002,timber);
    // Ladder rungs, iron bindings and small service landings.
    const liftHeight=a.top-y;
    for(let k=1;k<27;k++)box(px,y+k*liftHeight/27,pz+.00045,.0021,.00018,.00025,[.30,.25,.19]);
    for(let k=1;k<5;k++){
      const level=y+k*liftHeight/5;
      for(const dx of [-.002,.002])box(px+dx,level,pz+.0004,.00046,.00065,.00025,[.32,.36,.37]);
      box(px,level,pz-.0004,.0026,.00035,.0015,timber);
      face([px-.002,level,pz],[px-.0016,level,pz],[px+.002,level+liftHeight/5-.001,pz],[px+.0016,level+liftHeight/5-.001,pz],[.25,.20,.15]);
    }
    for(const dx of [-.0017,.0017])box(px+dx,y+.008,pz+.002,.00018,.003,.00018,[.31,.34,.34]);
    box(px,y+.0105,pz+.002,.0019,.0003,.0002,timber);
  }
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
 groups.push({isCastle:true,permanentNature:true,northWall:true,vao,count:mesh.indices.length,type:gl.UNSIGNED_INT,base:[1,1,1],emission:[.26,.28,.30],texture:northWallTexture,opacity:1});
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
