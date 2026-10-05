import {build} from 'esbuild';
import {readFile,writeFile} from 'node:fs/promises';
const bundle=await build({entryPoints:[new URL('./ui.mjs',import.meta.url).pathname],bundle:true,write:false,format:'esm',platform:'browser',minify:true,target:'es2022'});
const template=await readFile(new URL('./ui-template.html',import.meta.url),'utf8');
await writeFile(new URL('./ui.html',import.meta.url),template.replace('/* APP_SCRIPT */',()=>bundle.outputFiles[0].text.replace(/<\/script/gi,'<\\/script')));
