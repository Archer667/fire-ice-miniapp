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

export function buildIceWall({east,west}, sampleHeight) {
  const packed=[],indices=[];
  function face(a,b,c,d,color){
    const u=b.map((v,i)=>v-a[i]),v=c.map((v,i)=>v-a[i]);
    let n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
    const length=Math.hypot(...n)||1;n=n.map(v=>v/length);
    const offset=packed.length/10;for(const p of [a,b,c,d])packed.push(...p,...n,...color,1);
    indices.push(offset,offset+1,offset+2,offset,offset+2,offset+3);
  }
  const segments=72,depth=.011,height=.059;
  const nodes=Array.from({length:segments+1},(_,i)=>{
    const t=i/segments,x=west.x+(east.x-west.x)*t;
    const z=west.z+(east.z-west.z)*t+Math.sin(t*Math.PI)*Math.sin(t*11)*.002;
    const base=sampleHeight(x,z)?.height??.037;
    return {x,z,base,top:base+height+Math.sin(i*1.91)*.0013};
  });
  for(let i=0;i<segments;i++){
    const a=nodes[i],b=nodes[i+1],groove=i%3===0?.002:.0004;
    const pale=.84+(Math.sin(i*2.17)+1)*.025;
    // Broad tapered ice faces, irregular vertical ridges and a snow-covered walk.
    face([a.x,a.base,a.z+depth],[b.x,b.base,b.z+depth],[b.x,b.top,b.z+depth*.47-groove],[a.x,a.top,a.z+depth*.47-groove],[pale*.78,pale*.91,pale]);
    face([b.x,b.base,b.z-depth],[a.x,a.base,a.z-depth],[a.x,a.top,a.z-depth*.47],[b.x,b.top,b.z-depth*.47],[.78,.88,.94]);
    face([a.x,a.top,a.z-depth*.47],[a.x,a.top,a.z+depth*.47],[b.x,b.top,b.z+depth*.47],[b.x,b.top,b.z-depth*.47],[.96,.98,1]);
    for(const band of [.21,.48,.76]){
      const f=band+Math.sin(i*.73+band*9)*.017,thickness=.001;
      const point=(p,ratio)=>[p.x,p.base+(p.top-p.base)*ratio,p.z+depth-(depth*.53+groove)*ratio+.00015];
      face(point(a,f),point(b,f+.009),point(b,f+.009+thickness),point(a,f+thickness),[.62,.77,.85]);
    }
    if(i%4===0){
      const x=a.x+.0006,top=a.top-.006;
      face([x,top,a.z+depth*.6],[x+.0011,top,a.z+depth*.6],[x+.0006,top-.016,a.z+depth*.65],[x,top-.007,a.z+depth*.6],[.7,.85,.93]);
    }
  }
  for(const a of [nodes[0],nodes.at(-1)])face([a.x,a.base,a.z-depth],[a.x,a.base,a.z+depth],[a.x,a.top,a.z+depth*.47],[a.x,a.top,a.z-depth*.47],[.83,.91,.96]);
  // Small recessed gates below the ice; the castles remain on the southern side.
  for(const t of [.025,.55,.975]){
    const a=nodes[Math.round(t*segments)],z=a.z+depth+.0002,y=a.base;
    face([a.x-.0024,y,z],[a.x+.0024,y,z],[a.x+.0024,y+.010,z],[a.x-.0024,y+.010,z],[.10,.18,.22]);
    face([a.x-.0024,y+.010,z],[a.x+.0024,y+.010,z],[a.x+.0011,y+.012,z],[a.x-.0011,y+.012,z],[.10,.18,.22]);
  }
  return {packed:new Float32Array(packed),indices:new Uint32Array(indices),nodes};
}

export function enhanceLandmarkRuntime(source) {
  const marker="ctx.strokeStyle=color;ctx.lineWidth=close?2:3;ctx.stroke();";
  if(!source.includes(marker))throw Error('Flag frame integration point missing');
  source=source.replace(marker,"window.valyriaNorth.paintFlagFrame(ctx,x,y,r,color,close);");
  return source+`\n
let northWallKey='',northWallBuffers=[],northWallNodes=[],snowOverview=null;
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
 for(const loc of [3,4,5,6])gl.disableVertexAttribArray(loc);gl.vertexAttrib2f(3,0,0);gl.vertexAttrib1f(4,0);
 const ib=gl.createBuffer();northWallBuffers.push({buffer:ib});gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,mesh.indices,gl.STATIC_DRAW);
 groups.push({isCastle:true,permanentNature:true,northWall:true,vao,count:mesh.indices.length,type:gl.UNSIGNED_INT,base:[1,1,1],emission:[0,0,0],texture:null,opacity:1});
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
