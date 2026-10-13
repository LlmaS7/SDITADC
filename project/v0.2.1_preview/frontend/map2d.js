const colors = ['#43adf5', '#ffb154', '#6bcea7'];
const key = p => `${p[0]},${p[1]}`;

export class Map2D {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.map = null;
    this.cache = document.createElement('canvas');
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    this.resize();
  }
  resize() {
    const r = this.canvas.parentElement.getBoundingClientRect();
    this.width = Math.max(1, r.width); this.height = Math.max(1, r.height);
    this.dpr = Math.min(devicePixelRatio || 1, 2);
    this.canvas.width = Math.round(this.width * this.dpr);
    this.canvas.height = Math.round(this.height * this.dpr);
    this.rebuild();
  }
  setMap(map) { this.map = map; this.rebuild(); }
  rebuild() {
    if (!this.map) return;
    const m = this.map;
    this.cell = Math.min((this.width - 12) / m.width, (this.height - 12) / m.height);
    this.ox = (this.width - this.cell * m.width) / 2;
    this.oy = (this.height - this.cell * m.height) / 2;
    this.cache.width = this.canvas.width; this.cache.height = this.canvas.height;
    const c = this.cache.getContext('2d'); c.scale(this.dpr, this.dpr);
    c.fillStyle = '#dbe4e9'; c.fillRect(0, 0, this.width, this.height);
    const shelves = new Set(m.shelves.map(key)), obstacles = new Set(m.obstacles.map(key));
    const blocked = new Set(m.blocked.map(key));
    for (let y = 0; y < m.height; y++) for (let x = 0; x < m.width; x++) {
      const k = `${x},${y}`;
      c.fillStyle = shelves.has(k) ? '#61788c' : obstacles.has(k) ? '#ab8d68' : blocked.has(k) ? '#344b5d' : '#edf2f5';
      c.fillRect(this.ox + x*this.cell, this.oy + y*this.cell, this.cell, this.cell);
      c.strokeStyle = blocked.has(k) ? '#445e71' : '#cbd8e0'; c.lineWidth = .5;
      c.strokeRect(this.ox + x*this.cell, this.oy + y*this.cell, this.cell, this.cell);
      if (obstacles.has(k)) {
        const px = this.ox + x*this.cell, py = this.oy + y*this.cell;
        c.strokeStyle = '#745939'; c.beginPath(); c.moveTo(px+2,py+2); c.lineTo(px+this.cell-2,py+this.cell-2); c.stroke();
      }
    }
    for (const [points, color, label] of [[m.pickups,'#a7d1e3',i=>String(i+1)], [m.deliveries,'#a0d8b8',i=>`D${i+1}`], [m.parking,'#bbb8db',()=> 'P']]) {
      points.forEach((p,i) => {
        const [x,y] = this.center(p);
        c.fillStyle = color; c.fillRect(x-this.cell*.4,y-this.cell*.4,this.cell*.8,this.cell*.8);
        c.fillStyle = '#335367'; c.font = `${Math.max(8,this.cell*.59)}px Microsoft YaHei, sans-serif`;
        c.textAlign='center'; c.textBaseline='middle'; c.fillText(label(i),x,y);
      });
    }
  }
  center(p) { return [this.ox+(p[0]+.5)*this.cell, this.oy+(p[1]+.5)*this.cell]; }
  draw(state, positions, task) {
    if (!this.map || !state) return;
    const c = this.ctx; c.setTransform(1,0,0,1,0,0); c.drawImage(this.cache,0,0); c.scale(this.dpr,this.dpr);
    c.lineJoin='round'; c.lineCap='round';
    for (const r of state.robots) {
      if (r.path.length < 2) continue;
      c.strokeStyle = colors[r.id-1]+'99'; c.lineWidth = Math.max(1.4,this.cell*.13); c.beginPath();
      r.path.forEach((p,i) => { const [x,y]=this.center(p); i ? c.lineTo(x,y) : c.moveTo(x,y); }); c.stroke();
    }
    if (task) {
      for (const [p,color] of [[task.pickup,'#1684bc'],[task.delivery,'#229461']]) {
        const [x,y]=this.center(p); c.strokeStyle=color; c.lineWidth=2;
        c.beginPath(); c.arc(x,y,this.cell*.53,0,Math.PI*2); c.stroke();
      }
    }
    for (const r of state.robots) {
      const [x,y]=this.center(positions[r.id]); const radius=Math.max(4,this.cell*.4);
      c.fillStyle='#304353'; c.beginPath(); c.arc(x+.8,y+1,radius+.6,0,Math.PI*2); c.fill();
      c.fillStyle=colors[r.id-1]; c.beginPath(); c.arc(x,y,radius,0,Math.PI*2); c.fill();
      c.fillStyle='#183347'; c.font=`bold ${Math.max(8,this.cell*.57)}px sans-serif`; c.textAlign='center'; c.textBaseline='middle'; c.fillText(r.id,x,y);
      if (r.loaded) { c.fillStyle='#f7e5b1'; c.fillRect(x+radius*.35,y-radius*1.25,radius*.7,radius*.65); }
      if (r.urgent) { c.strokeStyle='#d85167'; c.lineWidth=1.7; c.beginPath(); c.arc(x,y,radius+2,0,Math.PI*2); c.stroke(); }
    }
    if (task) {
      const [x,y] = this.center(task.pickup); const size=Math.max(10,this.cell*.65);
      c.font=`${size}px Microsoft YaHei,sans-serif`; const width=size+5, height=size+4;
      c.fillStyle='#f5fafc'; c.fillRect(x-width/2,y-this.cell*.6-height,width,height);
      c.strokeStyle='#1684bc'; c.lineWidth=1; c.strokeRect(x-width/2,y-this.cell*.6-height,width,height);
      c.fillStyle='#1684bc'; c.textAlign='center'; c.textBaseline='middle'; c.fillText('取',x,y-this.cell*.6-height/2);
      const [dx,dy]=this.center(task.delivery);
      c.fillStyle='#229461'; c.fillText('送',dx,dy-this.cell*.95);
    }
    this.canvas.dataset.tick = state.tick;
  }
}
