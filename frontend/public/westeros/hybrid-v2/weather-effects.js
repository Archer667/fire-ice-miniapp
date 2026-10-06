// Bounded screen-space particles; independent of terrain rendering and frame rate.
export function createWeatherPainter(random = Math.random) {
  let particles = [], last = null, kind = 'none', opacity = 0;
  let wind = 0, targetWind = 0, gustIn = 0, pulse = 1, targetPulse = 1;
  function spawn(w, h, initial = false) {
    const depth = .25 + random() * .75;
    return { x: random() * (w + 80) - 40, y: initial ? random() * h : -20 - random() * 60,
      depth, speed: random(), phase: random() * Math.PI * 2, age: random() * 20,
      size: .5 + depth * 1.8, alpha: .15 + random() * .45 };
  }
  return function paint(ctx, w, h, weather, timestamp) {
    const dt = last === null ? 1 / 30 : Math.max(0, Math.min(.07, (timestamp - last) / 1000));
    last = timestamp;
    if (weather !== 'none' && weather !== kind) {
      kind = weather; particles = []; opacity = 0; gustIn = 0;
    }
    opacity += ((weather === 'none' ? 0 : 1) - opacity) * (1 - Math.exp(-dt * .7));
    if (opacity < .005) { particles = []; return; }
    gustIn -= dt;
    if (gustIn <= 0) {
      targetWind = (random() - .5) * (kind === 'rain' ? 100 : 32);
      targetPulse = .55 + random() * .45; gustIn = 3 + random() * 9;
    }
    wind += (targetWind - wind) * (1 - Math.exp(-dt * .5));
    pulse += (targetPulse - pulse) * (1 - Math.exp(-dt * .3));
    const count = Math.min(260, Math.max(45, Math.round(w * h / (kind === 'rain' ? 2300 : 3200))));
    while (particles.length < count) particles.push(spawn(w, h, true));
    if (particles.length > count) particles.length = count;
    ctx.save();
    for (let i = 0; i < particles.length; i++) {
      let p = particles[i]; p.age += dt;
      const vy = kind === 'rain' ? 260 + p.depth * 430 + p.speed * 170 : 13 + p.depth * 31 + p.speed * 14;
      const vx = wind * (.45 + p.depth) + (kind === 'snow' ? Math.sin(p.age * (.6 + p.speed) + p.phase) * 13 : 0);
      p.x += vx * dt; p.y += vy * dt;
      if (p.y > h + 25 || p.x < -65 || p.x > w + 65) {
        p = particles[i] = spawn(w, h);
        // Windward entry avoids an empty stripe when the wind changes direction.
        if (random() < .22 && Math.abs(wind) > 10) { p.x = wind > 0 ? -15 : w + 15; p.y = random() * h; }
      }
      const alpha = p.alpha * opacity * pulse;
      if (kind === 'rain') {
        const trail = .012 + p.depth * .021;
        ctx.lineWidth = .45 + p.depth * .7;
        ctx.strokeStyle = `rgba(190,213,229,${alpha * .65})`;
        ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - vx * trail, p.y - vy * trail); ctx.stroke();
      } else {
        ctx.fillStyle = `rgba(244,248,253,${alpha})`;
        ctx.beginPath(); ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.restore();
  };
}

export function enhanceWeatherRuntime(source) {
  const start = source.indexOf(" if(weather!=='none'){ctx.strokeStyle=");
  const end = source.indexOf(" if(center&&typeof paintCastleMarkers", start);
  if (start < 0 || end < 0) throw new Error('Weather integration point missing');
  source = source.slice(0, start) + ' paintNaturalWeather(ctx,w,h,weather,t);\n' + source.slice(end);
  source = source.replace(/const droplets=Array\.from\([^\n]+\);/, 'const paintNaturalWeather=window.createValyriaWeatherPainter();');
  // Keep the game season and admin probabilities, but vary each shower's boundaries.
  source = source.replace("return chance>=probability||phase<.08||phase>.92?'none':season===3?'snow':'rain';",
    "const wetStart=.03+((x>>>5)&255)/255*.16,wetEnd=.70+((x>>>17)&255)/255*.27;return chance>=probability||phase<wetStart||phase>wetEnd?'none':season===3?'snow':'rain';");
  return source;
}
