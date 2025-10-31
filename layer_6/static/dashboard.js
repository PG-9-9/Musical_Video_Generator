const server = window.SERVER_URL || '/';

function appendLog(text){
  const logs = document.getElementById('logs');
  logs.textContent += text + '\n';
  logs.scrollTop = logs.scrollHeight;
}

async function startJob(job){
  // gather inputs and POST a JSON body to /start
  const lyrics = document.getElementById('lyrics').value;
  const style = document.getElementById('style').value;
  const body = { job: job, args: { lyrics: lyrics, style: style } };
  const resp = await fetch('/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if(!resp.ok){
    console.error('Start failed: ' + resp.statusText);
    return null;
  }
  const j = await resp.json();
  pollStatus(j.jobid);
}

// note: logs are written server-side; we poll job metadata for progress

async function updateOutputs(){
  try{
    const r = await fetch('/api/outputs');
    if(!r.ok) return;
    const data = await r.json();
    const files = data.files || [];
    // categorize
    const wavs = files.filter(f=>f.endsWith('.wav')||f.endsWith('.mp3')||f.endsWith('.ogg'));
    const mp4s = files.filter(f=>f.endsWith('.mp4')||f.endsWith('.webm'));

    function chooseAudio(){
      const prefer = ['music_gen_test.wav','demo_music.wav','music.wav','test_music.wav'];
      for(let p of prefer){ if(wavs.includes(p)) return p; }
      return wavs.length? wavs[0] : null;
    }
    function chooseAnimation(){
      const prefer = ['animated.mp4','animation.mp4','video.mp4'];
      for(let p of prefer){ if(mp4s.includes(p)) return p; }
      // first non-final mp4
      for(let m of mp4s){ if(!m.includes('styled') && !m.includes('final')) return m; }
      return mp4s.length? mp4s[0] : null;
    }
    function chooseFinal(){
      // Prefer the final_with_audio (lyric video) when available, then styled_final, then final
      const prefer = ['final_with_audio.mp4','styled_final.mp4','final.mp4'];
      for(let p of prefer){ if(mp4s.includes(p)) return p; }
      return mp4s.length? mp4s[mp4s.length-1] : null;
    }

    const audioFile = chooseAudio();
    const animFile = chooseAnimation();
    const finalFile = chooseFinal();

    const audioEl = document.getElementById('audio-content');
    const animEl = document.getElementById('anim-content');
    const finalEl = document.getElementById('final-content');
    audioEl.innerHTML = '';
    animEl.innerHTML = '';
    finalEl.innerHTML = '';

    if(audioFile){
      const a = document.createElement('audio'); a.src = `/outputs/${audioFile}`; a.controls = true; a.style.width = '100%';
      audioEl.appendChild(a);
    } else {
      audioEl.textContent = 'No audio found.';
    }

    if(animFile){
      const v = document.createElement('video'); v.src = `/outputs/${animFile}`; v.controls = true; v.style.width = '100%';
      animEl.appendChild(v);
    } else {
      animEl.textContent = 'No animation found.';
    }

    if(finalFile){
      // Create a video player for the final file and ensure audio is enabled
      const v = document.createElement('video');
      v.src = `/outputs/${finalFile}`;
      v.controls = true;
      v.style.width = '100%';
      // Helpful hints to browsers: play inline, preload, and ensure not muted
      v.playsInline = true;
      try{ v.muted = false; }catch(e){}
      try{ v.volume = 1.0; }catch(e){}
      v.preload = 'auto';
      v.crossOrigin = 'anonymous';
      finalEl.appendChild(v);
    } else {
      finalEl.textContent = 'No final video found.';
    }
    // load Gemini analysis if present
    try{
      const g = await fetch('/outputs/lyrics_analysis.json');
      if(g.ok){
        const gj = await g.json();
        const gemEl = document.getElementById('gemini-content');
        gemEl.innerHTML = '';
        const list = document.createElement('div');
        if(gj.global_mood) list.appendChild(Object.assign(document.createElement('div'), {textContent: 'Global mood: ' + gj.global_mood}));
        if(gj.dominant_emotion) list.appendChild(Object.assign(document.createElement('div'), {textContent: 'Dominant emotion: ' + gj.dominant_emotion}));
        if(gj.recommended_bpm) list.appendChild(Object.assign(document.createElement('div'), {textContent: 'Recommended BPM: ' + gj.recommended_bpm}));
        if(gj.video_prompt) list.appendChild(Object.assign(document.createElement('div'), {textContent: 'Video prompt: ' + gj.video_prompt}));
        if(gj.music_prompt) list.appendChild(Object.assign(document.createElement('div'), {textContent: 'Music prompt: ' + gj.music_prompt}));
        gemEl.appendChild(list);
      }else{
        const gemEl = document.getElementById('gemini-content');
        gemEl.textContent = 'No Gemini analysis found.';
      }
    }catch(e){
      // ignore
    }
  }catch(e){ console.log(e); }
}

window.addEventListener('load', ()=>{
  document.getElementById('btn-music').addEventListener('click', ()=>startJob('music'));
  document.getElementById('btn-anim').addEventListener('click', ()=>startJob('anim'));
  document.getElementById('btn-style').addEventListener('click', ()=>startJob('style'));
  document.getElementById('btn-full').addEventListener('click', ()=>startJob('full'));
  updateOutputs();
});

// job ETA heuristics (seconds)
const ETA = { demo: 8, music: 30, anim: 40, style: 25, full: 180 };

async function pollStatus(jobid){
  // Poll job metadata and update progress bar using ETA heuristics. Logs are left on disk.
  const start = Date.now();
  while(true){
    try{
      const jobInfoR = await fetch(`/jobs/${jobid}`);
      if(!jobInfoR.ok){
        console.error('Job info fetch failed', jobInfoR.status);
        break;
      }
      const info = await jobInfoR.json();
      const jobname = info.job || 'full';
      // Prefer explicit progress emitted by the runner (server mirrors outputs/progress_*.json)
      if(info.progress !== undefined && info.progress !== null){
        document.getElementById('progress').value = info.progress;
      }else{
        const est = ETA[jobname] || 60;
        const created = info.created_at || (start/1000);
        const elapsed = (Date.now()/1000.0) - created;
        const pct = Math.min(99, Math.round((elapsed / est) * 100));
        document.getElementById('progress').value = pct;
      }
      if(info.status === 'finished' || info.status === 'error'){
        document.getElementById('progress').value = 100;
        // after finish, refresh outputs
        updateOutputs();
        break;
      }
    }catch(e){
      console.error('Polling failed', e);
      break;
    }
    await new Promise(r=>setTimeout(r, 800));
  }
}
