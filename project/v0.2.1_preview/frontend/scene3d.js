import * as THREE from 'three';
import { OrbitControls } from './vendor/OrbitControls.js';

const palette = [0x43adf5, 0xffb154, 0x6bcea7];

function label(text, color='#214253', background='#e6f2f6') {
  const canvas=document.createElement('canvas'); canvas.width=160; canvas.height=80;
  const c=canvas.getContext('2d'); c.fillStyle=background;
  c.beginPath(); c.roundRect(4,4,152,72,12); c.fill();
  c.fillStyle=color; c.font='bold 40px Microsoft YaHei,sans-serif'; c.textAlign='center'; c.textBaseline='middle'; c.fillText(text,80,40);
  const texture=new THREE.CanvasTexture(canvas); texture.colorSpace=THREE.SRGBColorSpace;
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false}));
  sprite.scale.set(.85,.425,1); return sprite;
}

function dispose(group) {
  group.traverse(object => {
    object.geometry?.dispose();
    const materials=Array.isArray(object.material) ? object.material : [object.material];
    materials.forEach(m => { m?.map?.dispose(); m?.dispose(); });
  });
  group.clear();
}

export class Scene3D {
  constructor(container) {
    this.container=container; this.robots=new Map(); this.paths=new Map();
    this.highlightKey=null; this.available=false;
    try {
      this.renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
      this.renderer.setPixelRatio(Math.min(devicePixelRatio || 1,2));
      this.renderer.setClearColor(0x202d38);
      this.renderer.outputColorSpace=THREE.SRGBColorSpace;
      this.renderer.toneMapping=THREE.ACESFilmicToneMapping;
      this.renderer.toneMappingExposure=1.1;
      container.prepend(this.renderer.domElement);
      this.scene=new THREE.Scene(); this.scene.fog=new THREE.Fog(0x202d38,65,120);
      this.camera=new THREE.PerspectiveCamera(38,1,.1,150);
      this.controls=new OrbitControls(this.camera,this.renderer.domElement);
      this.controls.enableDamping=true; this.controls.dampingFactor=.08;
      this.controls.minDistance=12; this.controls.maxDistance=90;
      this.controls.maxPolarAngle=Math.PI*.48;
      this.scene.add(new THREE.HemisphereLight(0xe9f5ff,0x5b6b67,2.4));
      const sun=new THREE.DirectionalLight(0xfff0d8,3.2); sun.position.set(8,30,10); this.scene.add(sun);
      this.warehouse=new THREE.Group(); this.scene.add(this.warehouse);
      this.highlights=new THREE.Group(); this.scene.add(this.highlights);
      this.available=true;
      this.renderer.domElement.addEventListener('webglcontextlost',e => { e.preventDefault(); this.available=false; this.error('3D 渲染连接中断，2D 与任务操作仍可使用。'); });
      new ResizeObserver(() => this.resize()).observe(container);
      this.resize();
    } catch (error) { this.error('当前环境未能启动 WebGL 2。2D 预览与任务操作仍可使用。'); console.error(error); }
  }
  error(message) { const e=document.getElementById('scene-error'); e.hidden=false; e.textContent=message; }
  resize() {
    if (!this.renderer) return;
    const r=this.container.getBoundingClientRect();
    this.renderer.setSize(Math.max(1,r.width),Math.max(1,r.height),false);
    this.camera.aspect=r.width/Math.max(1,r.height); this.camera.updateProjectionMatrix();
  }
  recenter() {
    if (!this.map || !this.available) return;
    const {width,height}=this.map;
    const damping=this.controls.enableDamping;
    this.controls.enableDamping=false; this.controls.update(); this.controls.enableDamping=damping;
    this.camera.position.set(width*1.06,37,height*1.52);
    this.controls.target.set(width/2,0,height/2);
    // Fit the full footprint in this panel, including its near corner.
    for(let attempt=0;attempt<10;attempt++) {
      this.camera.lookAt(this.controls.target); this.camera.updateMatrixWorld();
      const corners=[[0,0],[width,0],[0,height],[width,height]].map(([x,z])=>new THREE.Vector3(x,0,z).project(this.camera));
      if(corners.every(p=>Math.abs(p.x)<.91 && Math.abs(p.y)<.88)) break;
      this.camera.position.sub(this.controls.target).multiplyScalar(1.08).add(this.controls.target);
    }
    this.controls.update();
  }
  box(width,height,depth,color,x,y,z,group=this.warehouse) {
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(width,height,depth),
      new THREE.MeshStandardMaterial({color,roughness:.78,metalness:.12}));
    mesh.position.set(x,y,z); group.add(mesh); return mesh;
  }
  setMap(map) {
    this.map=map;
    if (!this.available) return;
    dispose(this.warehouse); dispose(this.highlights); this.highlightKey=null;
    for (const path of this.paths.values()) { this.scene.remove(path); path.geometry.dispose(); path.material.dispose(); }
    this.paths.clear();
    const {width,height}=map;
    const floor=new THREE.Mesh(new THREE.PlaneGeometry(width,height),new THREE.MeshStandardMaterial({color:0xd8e3e8,roughness:1}));
    floor.rotation.x=-Math.PI/2; floor.position.set(width/2,0,height/2); this.warehouse.add(floor);
    const coords=[];
    for(let x=0;x<=width;x++) coords.push(x,.012,0,x,.012,height);
    for(let z=0;z<=height;z++) coords.push(0,.012,z,width,.012,z);
    const grid=new THREE.BufferGeometry(); grid.setAttribute('position',new THREE.Float32BufferAttribute(coords,3));
    this.warehouse.add(new THREE.LineSegments(grid,new THREE.LineBasicMaterial({color:0x7f99aa,transparent:true,opacity:.32})));
    this.box(width,.38,1,0x466072,width/2,.19,.5);
    this.box(width,.38,1,0x466072,width/2,.19,height-.5);
    this.box(1,.38,height-2,0x466072,.5,.19,height/2);
    this.box(1,.38,height-2,0x466072,width-.5,.19,height/2);
    // Merge each connected rack footprint; no external 3D models are needed.
    const remaining=new Map(map.shelves.map(p=>[p.join(','),p]));
    while(remaining.size) {
      const first=remaining.values().next().value; const queue=[first], cells=[]; remaining.delete(first.join(','));
      while(queue.length) {
        const p=queue.pop(); cells.push(p);
        for(const q of [[p[0]+1,p[1]],[p[0]-1,p[1]],[p[0],p[1]+1],[p[0],p[1]-1]]) {
          if(remaining.has(q.join(','))) { remaining.delete(q.join(',')); queue.push(q); }
        }
      }
      const xs=cells.map(p=>p[0]), zs=cells.map(p=>p[1]);
      const x=Math.min(...xs), z=Math.min(...zs), w=Math.max(...xs)-x+1, d=Math.max(...zs)-z+1;
      this.box(w-.14,1.55,d-.14,0x637d90,x+w/2,.775,z+d/2);
      for(const y of [.38,.85,1.35]) this.box(w-.08,.055,d-.08,0x8fa9b8,x+w/2,y,z+d/2);
      this.box(w-.22,.16,d-.22,0x516b7c,x+w/2,1.63,z+d/2);
    }
    map.obstacles.forEach(([x,z])=>this.box(.8,.62,.8,0xad8e65,x+.5,.31,z+.5));
    for(const [points,color,prefix] of [[map.pickups,0x8dc9de,''],[map.deliveries,0x86cda8,'D'],[map.parking,0xaaa6d1,'P']]) {
      points.forEach(([x,z],index)=>{
        this.box(.85,.025,.85,color,x+.5,.025,z+.5);
        const s=label(prefix==='P' ? 'P' : prefix+(index+1));
        s.position.set(x+.5,.55,z+.5); this.warehouse.add(s);
      });
    }
    this.recenter();
  }
  robot(id) {
    if(this.robots.has(id)) return this.robots.get(id);
    const g=new THREE.Group(), color=palette[id-1];
    this.box(.7,.26,.88,color,0,.29,0,g);
    this.box(.52,.13,.62,0x354a5a,0,.48,0,g);
    for(const x of [-.36,.36]) for(const z of [-.28,.28]) this.box(.13,.18,.24,0x273843,x,.16,z,g);
    const cargo=this.box(.34,.3,.34,0xf1d59b,0,.69,0,g); cargo.visible=false;
    const number=label('R'+id,'#163444'); number.position.set(0,1.08,0); number.scale.set(.72,.36,1); g.add(number);
    const ring=new THREE.Mesh(new THREE.RingGeometry(.5,.58,32),new THREE.MeshBasicMaterial({color:0xf17b8c,side:THREE.DoubleSide}));
    ring.rotation.x=-Math.PI/2; ring.position.y=.04; ring.visible=false; g.add(ring);
    const result={group:g,cargo,ring}; this.robots.set(id,result); this.scene.add(g); return result;
  }
  update(state, task) {
    if(!this.available) return;
    for(const r of state.robots) {
      const robot=this.robot(r.id); robot.cargo.visible=r.loaded; robot.ring.visible=r.urgent;
      const old=this.paths.get(r.id); if(old) { this.scene.remove(old); old.geometry.dispose(); old.material.dispose(); }
      if(r.path.length>1) {
        const points=r.path.map(([x,z])=>new THREE.Vector3(x+.5,.075,z+.5));
        const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(points),new THREE.LineBasicMaterial({color:palette[r.id-1],transparent:true,opacity:.85}));
        this.scene.add(line); this.paths.set(r.id,line);
      } else this.paths.delete(r.id);
    }
    this.highlight(task);
  }
  highlight(task) {
    if(!this.available) return;
    const key=task ? task.id+':'+task.pickup.join(',')+':'+task.delivery.join(',') : null;
    if(key===this.highlightKey) return;
    dispose(this.highlights); this.highlightKey=key;
    if(task) for(const [p,color,word] of [[task.pickup,0x198abd,'取'],[task.delivery,0x21996e,'送']]) {
      const ring=new THREE.Mesh(new THREE.RingGeometry(.6,.69,40),new THREE.MeshBasicMaterial({color,side:THREE.DoubleSide}));
      ring.rotation.x=-Math.PI/2; ring.position.set(p[0]+.5,.06,p[1]+.5); this.highlights.add(ring);
      const s=label(word,'#174b58'); s.position.set(p[0]+.5,1.22,p[1]+.5); s.scale.set(.65,.325,1); this.highlights.add(s);
    }
  }
  draw(state, positions) {
    if(!this.available || !state) return;
    for(const r of state.robots) {
      const p=positions[r.id], robot=this.robot(r.id); robot.group.position.set(p[0]+.5,0,p[1]+.5);
      const dx=r.position[0]-r.previous[0], dz=r.position[1]-r.previous[1];
      if(dx || dz) robot.group.rotation.y=Math.atan2(dx,dz);
    }
    this.controls.update(); this.renderer.render(this.scene,this.camera);
    this.container.dataset.tick=state.tick;
  }
  inspect() {
    return {webgl2:this.available && typeof WebGL2RenderingContext!=='undefined' && this.renderer.getContext() instanceof WebGL2RenderingContext,
            robotCount:this.robots.size, drawCalls:this.renderer?.info.render.calls ?? 0,
            positions:[...this.robots.entries()].map(([id,r])=>({id,x:r.group.position.x-.5,y:r.group.position.z-.5}))};
  }
}
