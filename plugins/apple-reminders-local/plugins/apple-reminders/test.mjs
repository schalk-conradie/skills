import test from 'node:test';
import assert from 'node:assert/strict';
import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {InMemoryTransport} from '@modelcontextprotocol/sdk/inMemory.js';
import {createServer} from './server.mjs';
import {readFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

test('MCP tools validate dates, apply read defaults, preserve text, and report failures', async () => {
  const calls = [];
  const server = createServer(async (name, args) => {
    calls.push({name, args});
    if (args.reminder_id === 'missing') throw new Error('Reminder not found');
    return {id: 'test-reminder', ...args};
  });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const client = new Client({name: 'plugin-test', version: '1.0.0'});
  await server.connect(serverTransport);
  await client.connect(clientTransport);
  try {
    const {tools} = await client.listTools();
    assert.equal(tools.length, 8);
    const dashboard=tools.find(t=>t.name==='open_reminders');
    assert.equal(dashboard._meta.ui.resourceUri,'ui://apple-reminders/dashboard-v1.html');
    assert.deepEqual(dashboard._meta['openai/ui'].entrypoints,[{type:'global'},{type:'thread'}]);
    const resource=await client.readResource({uri:dashboard._meta.ui.resourceUri});
    assert.equal(resource.contents[0].mimeType,'text/html;profile=mcp-app');
    assert.match(resource.contents[0].text,/My Lists/);
    assert.doesNotMatch(resource.contents[0].text,/APP_SCRIPT/);
    assert.equal(tools.find(t => t.name === 'delete_reminder').annotations.destructiveHint, true);
    const read = await client.callTool({name: 'list_reminders', arguments: {}});
    assert.equal(read.isError, undefined);
    assert.deepEqual(calls[0], {name: 'list_reminders', args: {include_completed: false, limit: 50, offset: 0}});
    const title = 'Call "Sam"\n$(touch /tmp/never-run) \\ family';
    const created = await client.callTool({name: 'create_reminder', arguments: {title, due_at: '2026-10-02T09:00:00+02:00', remind_at: '2026-10-02T09:00:00+02:00'}});
    assert.equal(JSON.parse(created.content[0].text).title, title);
    const invalid = await client.callTool({name: 'create_reminder', arguments: {title: 'Test', due_at: 'tomorrow'}});
    assert.equal(invalid.isError, true);
    assert.equal(calls.length, 2);
    const blank = await client.callTool({name: 'create_reminder', arguments: {title: '   '}});
    assert.equal(blank.isError, true);
    const unknown = await client.callTool({name: 'delete_reminder', arguments: {reminder_id: 'missing'}});
    assert.equal(unknown.isError, true);
    assert.equal(unknown.content[0].text, 'Reminder not found');
    await client.callTool({name: 'complete_reminder', arguments: {reminder_id: 'test-reminder', completed: false}});
    assert.deepEqual(calls.at(-1).args, {reminder_id: 'test-reminder', completed: false});
  } finally {
    await client.close();
    await server.close();
  }
});

test('Reminders bridge creates, edits, completes, and deletes by ID without evaluating reminder text', async () => {
  const records = [];
  function reminder(props) {
    const record = {id: 'test-1', body: '', completed: false, dueDate: null, remindMeDate: null, alldayDueDate: null, flagged: false, priority: 0, ...props};
    const reference = {};
    reference.properties = () => ({...record});
    for (const key of Object.keys(record)) {
      Object.defineProperty(reference, key, {get: () => () => record[key], set: next => {record[key] = next;}});
    }
    return reference;
  }
  const target = {reminders: {push: r => records.push(r)}};
  const app = {
    defaultList: () => target,
    Reminder: reminder,
    reminders: {whose: filter => () => records.filter(r => r.id() === filter.id)},
    delete: r => records.splice(records.indexOf(r), 1),
  };
  const context = vm.createContext({Application: () => app});
  vm.runInContext(await readFile(new URL('./reminders.js', import.meta.url), 'utf8'), context);
  function invoke(operation, args) {
    return JSON.parse(context.run([JSON.stringify({operation, arguments: args})]));
  }
  const title = 'Call "Sam"\n\"; throw new Error("executed"); //';
  const created = invoke('create_reminder', {title, due_at: '2026-10-02T09:00:00+02:00', remind_at: '2026-10-02T09:00:00+02:00'});
  assert.equal(created.title, title);
  assert.equal(created.due_at, '2026-10-02T07:00:00.000Z');
  assert.equal(created.remind_at, '2026-10-02T07:00:00.000Z');
  const updated = invoke('update_reminder', {reminder_id: created.id, notes: 'New notes', priority: 5});
  assert.equal(updated.notes, 'New notes');
  assert.equal(updated.priority, 5);
  assert.equal(updated.title, title);
  assert.equal(updated.due_at, created.due_at);
  assert.equal(invoke('complete_reminder', {reminder_id: created.id, completed: true}).completed, true);
  assert.equal(invoke('complete_reminder', {reminder_id: created.id, completed: false}).completed, false);
  assert.deepEqual(invoke('delete_reminder', {reminder_id: created.id}), {deleted: true, id: created.id});
  assert.equal(records.length, 0);
  assert.throws(() => invoke('update_reminder', {reminder_id: created.id, title: 'Gone'}), /Reminder not found/);
});

test('Native bridge clamps calendar months and serializes timed and all-day reminders without saving them', () => {
  const stdout=execFileSync(fileURLToPath(new URL('./reminders-native',import.meta.url)),['--self-test'],{encoding:'utf8'});
  assert.match(stdout,/checks passed/);
});

for (const [today, cutoff] of [['2026-10-01T12:00:00Z', '2026-07-01'], ['2026-05-31T12:00:00Z', '2026-02-28']]) {
  test(`Presentation reads respect the completed-history cutoff from ${today}`, async () => {
    class ClockDate extends Date {constructor(...args){super(...(args.length?args:[today]));}}
    const boundary=new Date(`${cutoff}T00:00:00`);
    const rows=[{id:'active',completed:false,completionDate:null,flagged:true},
      {id:'recent',completed:true,completionDate:new Date(today),flagged:false},
      {id:'boundary',completed:true,completionDate:boundary,flagged:true},
      {id:'old',completed:true,completionDate:new Date(boundary.getTime()-1),flagged:false},
      {id:'unknown',completed:true,completionDate:null,flagged:false}];
    function matches(row,filter) {
      if(filter._or)return filter._or.some(f=>matches(row,f));
      if(filter._and)return filter._and.every(f=>matches(row,f));
      if('completed' in filter)return row.completed===filter.completed;
      return row.completionDate!==null&&row.completionDate>=filter.completionDate._greaterThanEquals;
    }
    function collection(selected) {
      return {whose:filter=>collection(selected.filter(row=>matches(row,filter))),id:()=>selected.map(r=>r.id),flagged:()=>selected.map(r=>r.flagged)};
    }
    const context=vm.createContext({Application:()=>({lists:()=>[],reminders:collection(rows)}),Date:ClockDate});
    vm.runInContext(await readFile(new URL('./reminders.js',import.meta.url),'utf8'),context);
    const invoke=include_completed=>JSON.parse(context.run([JSON.stringify({operation:'reminder_presentation',arguments:{include_completed}})]));
    assert.deepEqual(invoke(false).reminders,[{id:'active',flagged:true}]);
    assert.deepEqual(invoke(true).reminders,[{id:'active',flagged:true},{id:'recent',flagged:false},{id:'boundary',flagged:true}]);
  });
}
