import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
const python = resolve('.venv-engine', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
function run(cmd,args){const r=spawnSync(cmd,args,{stdio:'inherit'});if(r.status!==0)process.exit(r.status||1)}
if(!existsSync(python)){
  const interpreter=['python3.13','python3.12','python3.11','python3','python'].find(cmd=>{const r=spawnSync(cmd,['-c','import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] < (3, 14) else 1)']);return r.status===0});
  if(!interpreter){console.error('Install Python 3.11, 3.12, or 3.13, then run npm run local again.');process.exit(1)}
  run(interpreter,['-m','venv','.venv-engine']);
}
if(spawnSync(python,['-c','import libtorrent']).status!==0)run(python,['-m','pip','install','-r','engine/requirements.txt']);
const engine=spawn(python,['engine/server.py'],{stdio:'inherit',env:{...process.env,MEOW_ORIGIN:'http://localhost:5173'}});
const ui=spawn(process.execPath,['scripts/run-framework.mjs','dev','--host','127.0.0.1','--port','5173','--strictPort'],{stdio:'inherit',shell:process.platform==='win32'});
let stopping=false;
function stop(code=0){if(stopping)return;stopping=true;engine.kill('SIGINT');ui.kill('SIGTERM');process.exitCode=code}
engine.on('exit',code=>stop(code||0));ui.on('exit',code=>stop(code||0));
engine.on('error',e=>{console.error(e);stop(1)});ui.on('error',e=>{console.error(e);stop(1)});
process.on('SIGINT',()=>stop());process.on('SIGTERM',()=>stop());
console.log('Open http://localhost:5173 — downloads go to ~/Downloads/MeowTOrrent.');
