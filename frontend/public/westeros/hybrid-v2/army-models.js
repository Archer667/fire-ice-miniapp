// Two shared meshes: detail is uploaded once, while each army changes only uniforms.
export const REGION_COLORS = {north:'#ffffff',iron:'#172b50',river:'#677442',west:'#d6ad36',reach:'#6fae52',vale:'#b7def2',storm:'#92979d',dorne:'#e57932',crown:'#b82d32'};
const rgb = hex => [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16)/255);
export const bannerColor = campaign => rgb(REGION_COLORS[campaign.owner_region] || '#a99b7a');

export function buildArmyGeometry(sea) {
  const vertices=[], steel=[.62,.70,.74], light=[.86,.90,.90], dark=[.09,.13,.17], gold=[.83,.62,.27], wood=[.27,.13,.065], oak=[.46,.28,.13], ivory=[.89,.84,.69], cloth=[.8,.8,.8];
  function tri(a,b,c,color,part=0){const u=b.map((v,i)=>v-a[i]),v=c.map((q,i)=>q-a[i]),n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]],l=Math.hypot(...n)||1;for(const p of [a,b,c])vertices.push(...p,...n.map(q=>q/l),...color,part)}
  function quad(a,b,c,d,color,part=0){tri(a,b,c,color,part);tri(a,c,d,color,part)}
  function box(x,y,z,w,h,d,color,part=0){const p=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]].map(v=>[x+v[0]*w/2,y+v[1]*h/2,z+v[2]*d/2]);for(const q of [[0,3,2,1],[4,5,6,7],[0,4,7,3],[1,2,6,5],[3,7,6,2],[0,1,5,4]])quad(...q.map(i=>p[i]),color,part)}
  function rod(a,b,r,color,part=0,sides=7){const axis=b.map((v,i)=>v-a[i]),length=Math.hypot(...axis);if(!length)return;const n=axis.map(v=>v/length),ref=Math.abs(n[1])>.9?[1,0,0]:[0,1,0],u=[n[1]*ref[2]-n[2]*ref[1],n[2]*ref[0]-n[0]*ref[2],n[0]*ref[1]-n[1]*ref[0]],ul=Math.hypot(...u);u.forEach((v,i)=>u[i]=v/ul);const v=[n[1]*u[2]-n[2]*u[1],n[2]*u[0]-n[0]*u[2],n[0]*u[1]-n[1]*u[0]],point=(p,t)=>p.map((q,i)=>q+r*(u[i]*Math.cos(t)+v[i]*Math.sin(t)));for(let j=0;j<sides;j++){const t=j/sides*Math.PI*2,s=(j+1)/sides*Math.PI*2;quad(point(a,t),point(a,s),point(b,s),point(b,t),color,part);tri(b,point(b,t),point(b,s),color,part)}}
  function dome(x,y,z,rx,ry,rz,color){const steps=10,rings=4,point=(i,j)=>{const p=i/rings*Math.PI/2,t=j/steps*Math.PI*2;return [x+rx*Math.cos(p)*Math.cos(t),y+ry*Math.sin(p),z+rz*Math.cos(p)*Math.sin(t)]};for(let i=0;i<rings;i++)for(let j=0;j<steps;j++)quad(point(i,j),point(i,j+1),point(i+1,j+1),point(i+1,j),color)}
  function armor(x,z){const ring=(i,y,rx,rz)=>{const t=i/8*Math.PI*2;return [x+Math.cos(t)*rx,y,z+Math.sin(t)*rz]};for(let i=0;i<8;i++){quad(ring(i,.35,.13,.105),ring(i+1,.35,.13,.105),ring(i+1,.57,.17,.12),ring(i,.57,.17,.12),steel);quad(ring(i,.28,.16,.13),ring(i+1,.28,.16,.13),ring(i+1,.36,.13,.105),ring(i,.36,.13,.105),cloth,5);rod(ring(i,.37,.14,.11),ring(i+1,.37,.14,.11),.018,wood,0,5)}dome(x,.56,z,.15,.07,.11,steel)}
  function banner(x,y,z,width,height){rod([x,y-height-.2,z],[x,y+.09,z],.018,gold);for(let i=0;i<5;i++){const a=x+i/5*width,b=x+(i+1)/5*width,za=z+Math.sin(i/5*Math.PI)*.055,zb=z+Math.sin((i+1)/5*Math.PI)*.055;quad([a,y,za],[b,y,zb],[b,y-height+(i===4?.08:0),zb],[a,y-height,za],cloth,3);rod([a,y,za],[b,y,zb],.009,gold,3,4)}rod([x+.015,y-height*.5,z-.015],[x+width*.85,y-height*.5,z+.015],.014,gold,3,4)}
  if(!sea){
    for(const [index,x,z] of [[0,-.44,-.48],[1,.44,-.48],[2,0,.14],[3,-.44,.65],[4,.44,.65]]){
      const officer=index===2;
      for(const [side,part]of [[-1,1],[1,-1]]){rod([x+side*.075,.08,z],[x+side*.075,.35,z],.052,dark,part);rod([x+side*.075,.08,z+.03],[x+side*.075,.23,z+.03],.047,steel,part);box(x+side*.075,.045,z+.06,.11,.075,.18,dark,part)}
      armor(x,z);rod([x,.39,z+.125],[x,.54,z+.125],.014,gold);
      for(const side of [-1,1]){dome(x+side*.18,.56,z,.105,.08,.11,officer?gold:steel);rod([x+side*.19,.53,z],[x+side*.23,.33,z+.04],.045,steel)}
      rod([x,.59,z],[x,.67,z],.07,dark);dome(x,.68,z,.125,.17,.12,steel);
      box(x,.70,z+.10,.20,.095,.035,dark);rod([x,.65,z+.133],[x,.82,z+.133],.012,light);rod([x-.10,.74,z+.13],[x+.10,.74,z+.13],.012,light);
      if(officer){rod([x,.84,z-.10],[x,.89,z+.09],.025,gold);box(x,.58,z-.14,.24,.4,.026,cloth,5)}
      const sx=x-.24,sz=z+.11,outline=[[-.13,.53],[.13,.53],[.14,.36],[0,.20],[-.14,.36]];
      for(let i=0;i<outline.length;i++){const a=outline[i],b=outline[(i+1)%outline.length];tri([sx,.39,sz+.05],[sx+a[0],a[1],sz],[sx+b[0],b[1],sz],cloth,5);rod([sx+a[0],a[1],sz],[sx+b[0],b[1],sz],.013,gold,0,5)}
      rod([sx,.30,sz+.06],[sx,.48,sz+.06],.012,light);dome(sx,.39,sz+.06,.035,.035,.025,gold);
      rod([x+.23,.20,z],[x+.23,1.2,z],.013,wood);tri([x+.23,1.36,z],[x+.18,1.17,z],[x+.28,1.17,z],light);
    }
    banner(.17,1.95,.10,.67,.48);
  }else{
    const stations=[[-1.40,.02,.30],[-1.10,.31,.08],[-.70,.48,.02],[0,.54,0],[.65,.46,.04],[1.05,.28,.16],[1.43,.01,.42]];
    for(let i=0;i<stations.length-1;i++)for(const side of [-1,1]){
      const [za,wa,ya]=stations[i],[zb,wb,yb]=stations[i+1];
      for(let k=0;k<4;k++){const a=k/4,b=(k+1)/4;quad([side*wa*(.38+.62*a),ya-.35+.35*a,za],[side*wb*(.38+.62*a),yb-.35+.35*a,zb],[side*wb*(.38+.62*b),yb-.35+.35*b,zb],[side*wa*(.38+.62*b),ya-.35+.35*b,za],k%2?wood:oak)}
      quad([-wa,ya+.025,za],[wa,ya+.025,za],[wb,yb+.025,zb],[-wb,yb+.025,zb],oak);
      rod([side*wa,ya+.12,za],[side*wb,yb+.12,zb],.025,gold);
      rod([side*wa,ya-.04,za],[side*wb,yb-.04,zb],.018,dark);
      rod([side*wa,ya+.02,za],[side*wa,ya+.12,za],.013,wood);
    }
    for(let i=0;i<12;i++){const z=-1.04+i*.18;rod([-.29,.05,z],[.29,.05,z],.009,wood,0,4)}
    box(0,.23,-1.01,.51,.22,.37,wood);box(0,.29,1.00,.42,.24,.31,wood);
    for(const z of [-1.14,-.90,.90,1.13])for(const side of [-1,1])rod([side*.21,.32,z],[side*.21,.48,z],.013,gold);
    for(const side of [-1,1]){rod([side*.25,.48,-1.15],[side*.25,.48,-.88],.017,gold);rod([side*.21,.48,.88],[side*.21,.48,1.14],.017,gold)}
    for(const [z,height,width]of [[-.24,1.97,1.55],[.72,1.44,.92]]){
      rod([0,.02,z],[0,height+.16,z],.032,wood);rod([-width*.55,height-.2,z],[width*.55,height-.2,z],.022,wood);
      const point=(u,v)=>[(u-.5)*width,(height-.2)-v*(height*.56),z+Math.sin(u*Math.PI)*Math.sin(v*Math.PI)*.28];
      for(let i=0;i<10;i++)for(let j=0;j<7;j++){quad(point(i/10,j/7),point((i+1)/10,j/7),point((i+1)/10,(j+1)/7),point(i/10,(j+1)/7),ivory,i===4||i===5?3:4)}
      for(const side of [-1,1]){rod([0,height-.1,z],[side*.46,.08,z-.52],.008,dark,0,4);rod([side*width*.5,height-.2,z],[side*.38,.07,z+.43],.008,dark,0,4)}
    }
    for(let i=0;i<7;i++)for(const side of [-1,1]){const z=-.72+i*.22;rod([side*.36,-.01,z],[side*1.03,-.055,z-.14],.019,wood,2,5);box(side*1.05,-.05,z-.16,.18,.035,.13,oak,2)}
    rod([0,.30,1.24],[0,.66,1.57],.04,gold);dome(0,.65,1.57,.06,.09,.05,gold);
    banner(.01,2.38,-.24,.57,.28);banner(.01,.82,-1.08,.40,.25);
  }
  return new Float32Array(vertices);
}

function groundAt(heightAt,x,z){try{return heightAt(x,z)}catch{return null}}
export function isWaterPixel(r,g,b){return b>g+7&&b>r+13&&r<145}
const surfaceMasks=new WeakMap();
// Match the displayed coast, including terrain painted after the original height map.
export function visibleSurface(x,z,{heightAt,meta,center,yaw,pitch,overview}){
  const ground=groundAt(heightAt,x,z);if(!ground||!meta||!overview||!center)return ground;
  let cached=surfaceMasks.get(overview);
  if(!cached){const canvas=document.createElement('canvas');canvas.width=512;canvas.height=Math.round(512*overview.height/overview.width);const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(overview,0,0,canvas.width,canvas.height);const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data,mask=new Uint8Array(canvas.width*canvas.height);for(let i=0;i<mask.length;i++)mask[i]=isWaterPixel(pixels[i*4],pixels[i*4+1],pixels[i*4+2])?1:0;cached={mask,width:canvas.width,height:canvas.height};surfaceMasks.set(overview,cached)}
  const vx=x-center[0],vz=z-center[2],rx=vx*Math.cos(yaw)-vz*Math.sin(yaw),rz=vx*Math.sin(yaw)+vz*Math.cos(yaw),ay=(ground.height-center[1])*Math.cos(pitch)-rz*Math.sin(pitch),u=Math.floor((rx-meta.xmin)/(meta.span*meta.cols)*cached.width),v=Math.floor((meta.ymax-ay)/(meta.span*meta.rows)*cached.height);
  if(u<0||v<0||u>=cached.width||v>=cached.height)return ground;
  let water=0,total=0;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const px=u+dx,py=v+dy;if(px>=0&&py>=0&&px<cached.width&&py<cached.height){water+=cached.mask[py*cached.width+px];total++}}
  return {...ground,water:water>total/2};
}
const routeCache=new WeakMap();
function campaignPath(c,{findPlacement,routes}){
  const names=c.route_path?.length>1?c.route_path:[c.from,c.to],places=names.map(findPlacement);
  // Missing intermediate locations must not silently bridge unrelated legs.
  if(places.some(p=>!p)||places.length<2)return null;
  const cached=routeCache.get(c);if(cached&&cached.places.every((p,i)=>p===places[i])&&cached.places.length===places.length)return cached;
  const segments=[];
  for(let i=1;i<places.length;i++){
    const a=places[i-1],b=places[i],route=routes.find(r=>(r.a===a.id&&r.b===b.id)||(r.a===b.id&&r.b===a.id));
    let control=route?.points?.map(p=>p.slice())||[];
    const reverse=!!route&&route.a!==a.id;
    const world=p=>[p.position.x,p.position.y,p.position.z];
    if(control.length<2)control=reverse?[world(b),world(a)]:[world(a),world(b)];else{control[0]=world(reverse?b:a);control[control.length-1]=world(reverse?a:b)}
    const samples=[control[0]];
    for(let j=1;j<control.length-1;j++){
      const begin=samples.at(-1),handle=control[j],end=handle.map((v,k)=>(v+control[j+1][k])/2);
      for(let step=1;step<=8;step++){const t=step/8;samples.push(begin.map((v,k)=>(1-t)**2*v+2*(1-t)*t*handle[k]+t*t*end[k]))}
    }
    samples.push(control.at(-1));
    if(reverse)samples.reverse();
    for(let j=1;j<samples.length;j++){const a=samples[j-1],b=samples[j],length=Math.hypot(b[0]-a[0],b[2]-a[2]);if(length>1e-8)segments.push({a,b,length,sea:!!route?.sea})}
  }
  const result={places,segments,total:segments.reduce((s,p)=>s+p.length,0)};routeCache.set(c,result);return result;
}

export function campaignPose(c,tick,env){
  if(c.previewPose){const p={...c.previewPose,id:String(c.id),name:c.name,mine:c.mine,color:bannerColor(c)};if(p.end){const t=(Math.sin(tick/2500)+1)/2;p.position=p.position.map((v,i)=>v+(p.end[i]-v)*t)}return p}
  if(c.arrived)return null;
  const utc=v=>typeof v==='string'?Date.parse(/[zZ]$|[+-]\d\d:\d\d$/.test(v)?v:v+'Z'):NaN;
  const start=utc(c.departed_at),end=utc(c.arrival_at),progress=(tick-start)/(end-start);
  if(!Number.isFinite(progress)||end<=start||progress<0||progress>=1)return null;
  const path=campaignPath(c,env);if(!path?.total)return null;
  let remain=progress*path.total;
  for(const [index,segment]of path.segments.entries()){
    if(remain<=segment.length||index===path.segments.length-1){
      const {a,b}=segment,t=Math.max(0,Math.min(1,remain/segment.length)),position=a.map((v,i)=>v+(b[i]-v)*t),ground=groundAt(env.heightAt,position[0],position[2]);
      const sea=ground?!!ground.water:segment.sea;
      position[1]=sea?.034:(ground?.height??position[1])+.003;
      return {id:String(c.id),position,heading:Math.atan2(b[0]-a[0],b[2]-a[2]),sea,name:c.name,mine:c.mine,color:bannerColor(c)};
    }remain-=segment.length;
  }
  return null;
}

export function modelSize(zoom,height){return Math.max(.017,Math.min(.12,24/Math.max(1,zoom*height/2)))}

export function enhanceArmyRuntime(source){
  const start=source.indexOf('function buildArmyGeometry(sea){'),marker="window.addEventListener('message',e=>{if(e.origin===location.origin&&e.source===parent&&e.data?.type==='valyria-map-state')window.lastArmyStateTime=performance.now()});",end=source.indexOf(marker,start);
  if(start<0||end<0)throw Error('Army model integration point missing');
  source=source.slice(0,start)+`const armyLayer=window.valyriaArmies.createArmyLayer({canvas,findPlacement,routes:gameRouteLines,heightAt:(x,z)=>window.valyriaArmies.visibleSurface(x,z,{heightAt,meta:hybridMeta,center,yaw,pitch,overview:overviewImages.get(window.mapSeason||0)}),project:projectEffect,getScene:()=>({center,pitch,zoom,pan,state:gameState,placing}),onSelect:id=>{markerDown=null;pointerStart=null;parent.postMessage({type:'valyria-map-army',id},location.origin)}});
paintGameArmies=function(ctx){armyLayer.paint(ctx)};
`+source.slice(end+marker.length);
  const legacy=source.indexOf("canvas.addEventListener('pointerup',e=>{if(!markerDown||");
  if(legacy<0)throw Error('Army selection integration point missing');
  const legacyEnd=source.indexOf('\n',legacy);source=source.slice(0,legacy)+source.slice(legacyEnd);
  return source;
}

export function createArmyLayer(env){
  const canvas=document.createElement('canvas');canvas.id='army-models';canvas.style.cssText='position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:3';document.body.appendChild(canvas);
  const gl=canvas.getContext('webgl2',{alpha:true,antialias:true}),meshes={};let poses=[],hits=[],receivedAt=performance.now(),lastNow=null,lastFrame=0;
  function shader(type,text){const s=gl.createShader(type);gl.shaderSource(s,text);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
  let program,uniforms;
  if(gl){
    program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,`#version 300 es
precision highp float;layout(location=0)in vec3 p;layout(location=1)in vec3 n;layout(location=2)in vec3 color;layout(location=3)in float part;
uniform vec3 origin,center,banner;uniform float heading,size,pitch,zoom,aspect,phase;uniform vec2 pan;out vec3 C;out vec3 N;
void main(){vec3 q=p;if(abs(part)==1.)q.z+=sin(phase*7.+p.x*3.)*part*.09;if(part==2.)q.y+=sin(phase*3.+p.z*3.)*.055;if(part==3.||part==4.)q.z+=sin(phase*3.4+p.x*3.+p.y)*.035;
float c=cos(heading),s=sin(heading);q=vec3(q.x*c+q.z*s,q.y,-q.x*s+q.z*c)*size+origin-center;
gl_Position=vec4(q.x*zoom/aspect+pan.x,(q.y*cos(pitch)-q.z*sin(pitch))*zoom-.10+pan.y,-(q.z*cos(pitch)+q.y*sin(pitch))*.035,1.);
C=part==3.?banner:part==5.?mix(banner,vec3(.18),.20):color;N=vec3(n.x*c+n.z*s,n.y,-n.x*s+n.z*c);}`));
    gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`#version 300 es
precision highp float;in vec3 C;in vec3 N;out vec4 outColor;
void main(){vec3 normal=normalize(N);float light=.66+.34*abs(dot(normal,normalize(vec3(-.6,1.,-.55))));outColor=vec4(C*light,1.);}`));
    gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));
    uniforms=Object.fromEntries(['origin','center','banner','heading','size','pitch','zoom','aspect','phase','pan'].map(key=>[key,gl.getUniformLocation(program,key)]));
    for(const sea of [false,true]){const packed=buildArmyGeometry(sea),vao=gl.createVertexArray();gl.bindVertexArray(vao);gl.bindBuffer(gl.ARRAY_BUFFER,gl.createBuffer());gl.bufferData(gl.ARRAY_BUFFER,packed,gl.STATIC_DRAW);for(const [loc,size,off]of [[0,3,0],[1,3,12],[2,3,24],[3,1,36]]){gl.enableVertexAttribArray(loc);gl.vertexAttribPointer(loc,size,gl.FLOAT,false,40,off)}const bounds={min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]};for(let i=0;i<packed.length;i+=10)for(let j=0;j<3;j++){bounds.min[j]=Math.min(bounds.min[j],packed[i+j]);bounds.max[j]=Math.max(bounds.max[j],packed[i+j])}meshes[sea?'sea':'land']={vao,count:packed.length/10,bounds}}
    gl.enable(gl.DEPTH_TEST);
  }
  function update(scene,t){
    if(scene.state.now!==lastNow){lastNow=scene.state.now;receivedAt=t}
    const tick=(scene.state.now??Date.now())+(scene.state.paused?0:Math.min(2000,t-receivedAt));
    poses=scene.state.showArmies===false?[]:(scene.state.campaigns||[]).map(c=>campaignPose(c,tick,env)).filter(Boolean);
  }
  function boundsFor(p,scene,size){
    const bounds=meshes[p.sea?'sea':'land']?.bounds||{min:[-.8,-.4,-1.5],max:[.8,2.4,1.6]},projected=[];
    for(const x of [bounds.min[0],bounds.max[0]])for(const y of [bounds.min[1],bounds.max[1]])for(const z of [bounds.min[2],bounds.max[2]]){const c=Math.cos(p.heading||0),s=Math.sin(p.heading||0);projected.push(env.project([p.position[0]+(x*c+z*s)*size,p.position[1]+y*size,p.position[2]+(-x*s+z*c)*size]))}
    const xs=projected.map(p=>p[0]),ys=projected.map(p=>p[1]),x=(Math.min(...xs)+Math.max(...xs))/2,y=(Math.min(...ys)+Math.max(...ys))/2;
    return {id:p.id,x,y,rx:Math.max(23,(Math.max(...xs)-Math.min(...xs))/2+5),ry:Math.max(23,(Math.max(...ys)-Math.min(...ys))/2+5)};
  }
  function frame(t){
    requestAnimationFrame(frame);if(document.hidden||t-lastFrame<50)return;lastFrame=t;
    const scene=env.getScene();if(!scene.center)return;update(scene,t);
    const w=env.canvas.clientWidth,h=env.canvas.clientHeight,dpr=Math.min(devicePixelRatio,1.75);
    if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr)}
    if(gl){gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.useProgram(program);for(const [key,value]of Object.entries({pitch:scene.pitch,zoom:scene.zoom,aspect:w/h,phase:t/1000}))gl.uniform1f(uniforms[key],value);gl.uniform2fv(uniforms.pan,scene.pan);gl.uniform3fv(uniforms.center,scene.center)}
    hits=[];
    for(const p of poses){
      const [x,y]=env.project(p.position);if(x< -100||y< -100||x>w+100||y>h+100)continue;
      const size=p.size||modelSize(scene.zoom,h);hits.push(boundsFor(p,scene,size));
      if(!gl)continue;const mesh=meshes[p.sea?'sea':'land'];gl.bindVertexArray(mesh.vao);gl.uniform3fv(uniforms.origin,p.position);gl.uniform3fv(uniforms.banner,p.color);gl.uniform1f(uniforms.heading,p.heading||0);gl.uniform1f(uniforms.size,size);gl.drawArrays(gl.TRIANGLES,0,mesh.count);
    }
  }
  requestAnimationFrame(frame);
  const pointers=new Map();let multi=false;
  env.canvas.addEventListener('pointerdown',e=>{if(!pointers.size)multi=false;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY,moved:false});if(pointers.size>1)multi=true},{capture:true});
  env.canvas.addEventListener('pointermove',e=>{const p=pointers.get(e.pointerId);if(p&&Math.hypot(e.clientX-p.x,e.clientY-p.y)>7)p.moved=true},{capture:true});
  env.canvas.addEventListener('pointercancel',e=>{pointers.delete(e.pointerId);multi=true},{capture:true});
  env.canvas.addEventListener('pointerup',e=>{
    const down=pointers.get(e.pointerId);pointers.delete(e.pointerId);
    if(!down||down.moved||multi||env.getScene().placing||(e.button!==0&&e.button!==-1)||Math.hypot(e.clientX-down.x,e.clientY-down.y)>7)return;
    const rect=env.canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
    const hit=hits.filter(h=>Math.abs(x-h.x)<=h.rx&&Math.abs(y-h.y)<=h.ry).sort((a,b)=>Math.hypot(x-a.x,y-a.y)-Math.hypot(x-b.x,y-b.y))[0];
    if(hit){env.canvas.onpointerup?.(e);e.stopImmediatePropagation();env.onSelect(hit.id)}
  },{capture:true});
  return {paint(ctx){
    ctx.save();for(const p of poses){const [x,y]=env.project(p.position);if(x< -80||y< -80||x>env.canvas.clientWidth+80||y>env.canvas.clientHeight+80)continue;
      ctx.fillStyle='#0b101c55';ctx.beginPath();ctx.ellipse(x,y+3,p.sea?18:16,5,0,0,Math.PI*2);ctx.fill();
      ctx.strokeStyle=p.mine?'#f1cf78aa':'#f3e8c155';ctx.lineWidth=1.15;ctx.beginPath();ctx.ellipse(x,y+3,p.sea?21:19,7,0,0,Math.PI*2);ctx.stroke();
      if(p.sea){ctx.strokeStyle='#d9f3ff88';ctx.beginPath();ctx.moveTo(x-15,y+8);ctx.quadraticCurveTo(x,y+13,x+15,y+8);ctx.stroke()}
      if(!gl){ctx.font='22px sans-serif';ctx.fillStyle='#f1e4c2';ctx.fillText(p.sea?'⛵':'⚔',x-11,y)}
    }ctx.restore();
  }};
}
