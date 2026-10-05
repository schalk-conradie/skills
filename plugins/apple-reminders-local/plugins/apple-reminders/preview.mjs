import {createServer as httpServer} from 'node:http';
import {randomBytes} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {InMemoryTransport} from '@modelcontextprotocol/sdk/inMemory.js';
import {createServer} from './server.mjs';

const token=randomBytes(32).toString('hex');
const client=new Client({name:'reminders-local-panel',version:'1.1.0'});
const [clientTransport,serverTransport]=InMemoryTransport.createLinkedPair();
await createServer().connect(serverTransport);await client.connect(clientTransport);
const html=await readFile(new URL('./ui.html',import.meta.url),'utf8');
let origin;
const server=httpServer(async(request,response)=>{
  response.setHeader('Cache-Control','no-store');response.setHeader('X-Content-Type-Options','nosniff');
  if(request.headers.host!==new URL(origin).host){response.writeHead(403).end();return;}
  if(request.method==='GET'&&request.url==='/'){
    response.setHeader('Content-Type','text/html; charset=utf-8');
    response.setHeader('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src data:; frame-ancestors 'self'");
    response.end(html.replace('<title>',`<meta name="local-bridge" content="${token}"><title>`));return;
  }
  if(request.method!=='POST'||request.url!=='/api/call'){response.writeHead(404).end();return;}
  if(request.headers.origin!==origin||request.headers['x-reminders-token']!==token){response.writeHead(403).end();return;}
  try{
    let body='';for await(const chunk of request){body+=chunk;if(body.length>20000){response.writeHead(413).end();return;}}
    const result=await client.callTool(JSON.parse(body),undefined,{timeout:210000});
    response.setHeader('Content-Type','application/json');response.end(JSON.stringify(result));
  }catch(error){response.writeHead(400,{'Content-Type':'application/json'}).end(JSON.stringify({isError:true,content:[{type:'text',text:error.message}]}));}
});
server.listen(Number(process.argv[2] || 0),'127.0.0.1',()=>{origin=`http://127.0.0.1:${server.address().port}`;console.log(origin);});
process.on('SIGTERM',()=>{server.close();client.close();});
