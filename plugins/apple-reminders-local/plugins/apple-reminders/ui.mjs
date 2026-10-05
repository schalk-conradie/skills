import {App} from '@modelcontextprotocol/ext-apps';

const $ = id => document.getElementById(id);
const icons = {
  today:'<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 9h16M10 12h2v5"/>',
  scheduled:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h.01M12 14h.01M17 14h.01M7 17h.01M12 17h.01"/>',
  all:'<path d="M4 5h16l2 8v7H2v-7l2-8Z"/><path d="M2 13h6l2 3h4l2-3h6"/>',
  flagged:'<path d="M5 22V3c5-4 9 4 15 0v11c-6 4-10-4-15 0"/>',
  overdue:'<circle cx="12" cy="13" r="8"/><path d="M12 9v5l3 2M5 3 2 6M19 3l3 3"/>',
  completed:'<path d="m5 12 4 4L20 5"/>',
  list:'<path d="M9 6h12M9 12h12M9 18h12M3 6h.01M3 12h.01M3 18h.01"/>',
  monitor:'<rect x="2" y="3" width="20" height="14" rx="1"/><path d="M8 21h8M12 17v4"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  refresh:'<path d="M20 7v5h-5M4 17v-5h5"/><path d="M6 6a8 8 0 0 1 14 6M18 18a8 8 0 0 1-14-6"/>',
  plus:'<path d="M12 4v16M4 12h16"/>',
  search:'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
};
function svg(name) {return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name]}</svg>`;}
const cards = [{id:'today',name:'Today',color:'#60adea'},{id:'scheduled',name:'Scheduled',color:'#ef818a'},
  {id:'all',name:'All',color:'#dddde1'},{id:'flagged',name:'Flagged',color:'#efb784'},
  {id:'overdue',name:'Overdue',color:'#e770a0'},{id:'completed',name:'Completed',color:'#a0aab2'}];
let snapshot, selected, showCompleted = false, busy = false, editing;
let call, historyLoading=false, presentationRunning=false, presentationAgain=false, generation=0;
const app = new App({name:'Apple Reminders',version:'1.1.0'}, {}, {autoResize:true});
function unpack(response) {
  if(response.isError) throw new Error(response.content?.find(c=>c.type==='text')?.text || 'Reminders operation failed');
  return response.structuredContent || JSON.parse(response.content.find(c=>c.type==='text').text);
}
function localDay(date) {const d=new Date(date);return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;}
function matches(reminder, view) {
  if(view==='completed') return reminder.completed;
  if(reminder.completed) return false;
  const due = reminder.due_at || reminder.all_day_due_at;
  if(view==='today') return due && localDay(due)===localDay(new Date());
  if(view==='scheduled') return Boolean(due);
  if(view==='flagged') return reminder.flagged;
  if(view==='overdue') return due && (reminder.due_at===reminder.all_day_due_at ? localDay(due)<localDay(new Date()) : new Date(due)<new Date());
  return view==='all' || reminder.list_id===view;
}
function listColor(list,index=0) {
  return /^#[0-9a-f]{6}$/i.test(list.color || '') ? list.color : ['#f4b500','#1aaae7','#fc3b75','#ce7bf4','#188bff'][index%5];
}
function selectedColor() {
  const card=cards.find(c=>c.id===selected);
  const index=snapshot?.lists.findIndex(l=>l.id===selected);
  return card?.color || (index>=0 ? listColor(snapshot.lists[index],index) : '#ce7bf4');
}
function dateLabel(reminder) {
  const due=reminder.due_at || reminder.all_day_due_at;
  if(!due) return '';
  const day=localDay(due), today=localDay(new Date()), tomorrow=new Date();tomorrow.setDate(tomorrow.getDate()+1);
  const label=day===today?'Today':day===localDay(tomorrow)?'Tomorrow':new Date(due).toLocaleDateString(undefined,{month:'short',day:'numeric',year:new Date(due).getFullYear()!==new Date().getFullYear()?'numeric':undefined});
  return reminder.due_at===reminder.all_day_due_at ? label : `${label}, ${new Date(due).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'})}`;
}
function select(view) {selected=view;showCompleted=false;render();if(view==='completed')loadHistory();}
function renderNavigation() {
  $('tiles').replaceChildren();
  for(const card of cards) {
    const button=document.createElement('button');button.className=`tile ${card.id}`;button.setAttribute('aria-current',String(selected===card.id));
    button.innerHTML=`<span class="icon">${svg(card.id)}</span><span class="count"></span><span class="label">${card.name}</span>`;
    button.querySelector('.count').textContent=!snapshot || (card.id==='completed'&&!snapshot.history_loaded) || (card.id==='flagged'&&snapshot.reminders.some(r=>!r.completed&&typeof r.flagged!=='boolean'))?'—':snapshot.reminders.filter(r=>matches(r,card.id)).length;
    button.disabled=!snapshot || busy;button.onclick=()=>select(card.id);$('tiles').append(button);
  }
  $('lists').replaceChildren();
  snapshot?.lists.forEach((list,index)=>{
    const button=document.createElement('button');button.className='list';button.setAttribute('aria-current',String(selected===list.id));button.style.setProperty('--list-color',listColor(list,index));
    button.innerHTML=`<span class="badge">${svg(list.emblem?.toLowerCase().includes('tv')?'monitor':'list')}</span><span class="list-name"></span><span class="list-count"></span>`;
    button.querySelector('.list-name').textContent=list.name;
    button.querySelector('.list-count').textContent=snapshot.reminders.filter(r=>r.list_id===list.id&&!r.completed).length;
    button.onclick=()=>select(list.id);button.disabled=busy;$('lists').append(button);
  });
}
function render() {
  renderNavigation();
  $('refresh').disabled=busy;$('new').disabled=!snapshot || busy;$('add-row').disabled=!snapshot || busy;
  if(!snapshot) return;
  document.documentElement.style.setProperty('--accent',selectedColor());
  const query=$('search').value.trim().toLowerCase();
  const card=cards.find(c=>c.id===selected), list=snapshot.lists.find(l=>l.id===selected);
  $('heading').textContent=query?'Search results':card?.name || list?.name || 'Reminders';
  const completedInList=snapshot.reminders.filter(r=>r.list_id===selected&&r.completed);
  $('completed-count').textContent=!snapshot.history_loaded&&(list||selected==='completed')?'Completed history loads on demand':list?`${completedInList.length} Completed`:selected==='completed'?`${snapshot.reminders.filter(r=>r.completed).length} Completed`:'Incomplete reminders';
  $('show-completed').hidden=!list;$('show-completed').textContent=showCompleted?'Hide':'Show';
  let reminders=snapshot.reminders.filter(r=>query?(selected==='completed'?r.completed:!r.completed):matches(r,selected)||(showCompleted&&list&&r.list_id===selected));
  if(query) reminders=reminders.filter(r=>`${r.title} ${r.notes || ''}`.toLowerCase().includes(query));
  reminders.sort((a,b)=>Number(a.completed)-Number(b.completed));
  $('heading-count').textContent=reminders.filter(r=>!r.completed).length || (selected==='completed'?reminders.length:'0');
  $('reminders').replaceChildren();
  if(!reminders.length) {
    const empty=document.createElement('div');empty.className='empty';empty.innerHTML=`${svg('completed')}<strong></strong><span></span>`;
    empty.querySelector('strong').textContent=historyLoading&&selected==='completed'?'Loading recent completed reminders':selected==='flagged'&&snapshot.reminders.some(r=>!r.completed&&typeof r.flagged!=='boolean')?'Reading flag states':query?'No matching reminders':selected==='completed'?'No completed reminders':'All clear';
    empty.querySelector('span').textContent=historyLoading?'Last three months only.':selected==='flagged'&&snapshot.reminders.some(r=>!r.completed&&typeof r.flagged!=='boolean')?'Other lists are ready to use.':query?'Try a different title or note.':'Add a reminder when something comes to mind.';$('reminders').append(empty);
  }
  for(const reminder of reminders) {
    const row=document.createElement('article');row.className=`reminder${reminder.completed?' done':''}`;
    const check=document.createElement('button');check.className='check';check.setAttribute('aria-label',`${reminder.completed?'Reopen':'Complete'} ${reminder.title}`);check.setAttribute('aria-pressed',String(reminder.completed));check.innerHTML=reminder.completed?svg('completed'):'';check.disabled=busy;
    check.onclick=()=>mutate('complete_reminder',{reminder_id:reminder.id,completed:!reminder.completed});
    const content=document.createElement('div');content.className='reminder-content';
    const title=document.createElement('button');title.className='reminder-title';title.textContent=reminder.title;title.onclick=()=>openEditor(reminder);title.disabled=busy;content.append(title);
    if(reminder.notes){const notes=document.createElement('div');notes.className='subtitle';notes.textContent=reminder.notes;content.append(notes);}
    const label=dateLabel(reminder);if(label){const date=document.createElement('div');date.className=`subtitle date${matches(reminder,'overdue')?' overdue':''}`;date.textContent=label;content.append(date);}
    if(!list){const name=document.createElement('div');name.className='subtitle';name.textContent=reminder.list_name;content.append(name);}
    const actions=document.createElement('div');actions.className='reminder-actions';if(reminder.flagged){const flag=document.createElement('span');flag.className='flag';flag.innerHTML=svg('flagged');flag.title='Flagged';actions.append(flag);}
    const details=document.createElement('button');details.className='details';details.innerHTML=svg('info');details.setAttribute('aria-label',`Edit ${reminder.title}`);details.onclick=()=>openEditor(reminder);details.disabled=busy;actions.append(details);
    row.append(check,content,actions);$('reminders').append(row);
  }
  $('status').textContent=busy?'Syncing with Apple Reminders...':`Updated ${new Date(snapshot.fetched_at).toLocaleTimeString(undefined,{hour:'2-digit',minute:'2-digit'})} · Completed history: last 3 months`;
}
function accept(response) {snapshot=unpack(response);generation++;if(!selected)selected=snapshot.lists.find(l=>l.name==='Dataloop')?.id||snapshot.default_list_id;$('connection').textContent='Connected';render();}
function showError(error) {$('error').textContent=error.message;$('error').hidden=false;}
async function refresh() {
  if(busy)return;busy=true;$('error').hidden=true;render();
  try{accept(await call('open_reminders',{}));}catch(error){showError(error);$('connection').textContent='Connection issue';}
  finally{busy=false;render();}
  if(snapshot){if(selected==='completed'||showCompleted)await loadHistory();else loadPresentation();}
}
async function loadHistory() {
  if(busy||!snapshot||snapshot.history_loaded||historyLoading)return;
  historyLoading=true;busy=true;$('error').hidden=true;render();const current=generation;
  try {
    const reminders=[];let offset=0,total;
    do {const page=unpack(await call('list_reminders',{include_completed:true,limit:200,offset}));reminders.push(...page.reminders);total=page.total;offset+=page.reminders.length;if(offset<total&&!page.reminders.length)throw new Error('Completed history changed while loading. Refresh to try again.');} while(offset<total);
    if(current!==generation)return;
    const previous=new Map(snapshot.reminders.map(r=>[r.id,r]));
    snapshot.reminders=reminders.map(r=>({...r,flagged:previous.get(r.id)?.flagged}));snapshot.history_loaded=true;
    loadPresentation();
  } catch(error){if(current===generation)showError(error);}
  finally{historyLoading=false;busy=false;render();}
}
async function loadPresentation() {
  if(presentationRunning){presentationAgain=true;return;}
  presentationRunning=true;const current=generation;
  try {
    const details=unpack(await call('reminder_presentation',{include_completed:snapshot.history_loaded}));
    if(current!==generation){presentationAgain=true;return;}
    const flags=new Map(details.reminders.map(r=>[r.id,r.flagged]));
    snapshot.reminders.forEach(r=>{if(typeof r.flagged!=='boolean'&&flags.has(r.id))r.flagged=flags.get(r.id);});
    snapshot.lists.forEach(list=>Object.assign(list,details.lists.find(l=>l.id===list.id)||{}));render();
  }catch(error){if(current===generation)showError(new Error('Flag and list details could not load: '+error.message));}
  finally{presentationRunning=false;if(presentationAgain){presentationAgain=false;loadPresentation();}}
}
async function mutate(name,args) {
  if(busy)return;busy=true;render();$('error').hidden=true;
  try{applyMutation(name,args,unpack(await call(name,args)));}
  catch(error){showError(error);}finally{busy=false;render();}
}
function applyMutation(name,args,result) {
  if(name==='delete_reminder')snapshot.reminders=snapshot.reminders.filter(r=>r.id!==args.reminder_id);
  else {
    const index=snapshot.reminders.findIndex(r=>r.id===result.id);
    const listId=index>=0?snapshot.reminders[index].list_id:args.list_id || snapshot.default_list_id;
    const reminder={...(index>=0?snapshot.reminders[index]:{}),...result,list_id:listId,list_name:snapshot.lists.find(l=>l.id===listId)?.name || ''};
    if(index>=0)snapshot.reminders[index]=reminder;else snapshot.reminders.push(reminder);
  }
  snapshot.fetched_at=new Date().toISOString();render();
}
function localInput(iso) {if(!iso)return '';const date=new Date(iso);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);}
function openEditor(reminder) {
  if(busy||!snapshot)return;editing=reminder;$('form').reset();$('form-error').textContent='';
  $('editor-title').textContent=reminder?'Reminder details':'New reminder';$('save').textContent=reminder?'Save':'Add';$('delete').hidden=!reminder;
  $('title').value=reminder?.title || '';$('notes').value=reminder?.notes || '';
  $('due').value=localInput(reminder?.due_at);$('priority').value=String(reminder?.priority<=4&&reminder?.priority>0?1:reminder?.priority===5?5:reminder?.priority>5?9:0);$('flagged').checked=reminder?.flagged || false;$('flagged').disabled=Boolean(reminder)&&typeof reminder.flagged!=='boolean';
  $('list-choice').replaceChildren();for(const list of snapshot.lists){const option=document.createElement('option');option.value=list.id;option.textContent=list.name;$('list-choice').append(option);}
  $('list-choice').value=reminder?.list_id || (snapshot.lists.some(l=>l.id===selected)?selected:snapshot.default_list_id);$('list-choice').disabled=Boolean(reminder);
  $('editor').showModal();$('title').focus();
}
async function save(event) {
  event.preventDefault();if(busy)return;const args={title:$('title').value.trim(),notes:$('notes').value,priority:Number($('priority').value)};if(!$('flagged').disabled)args.flagged=$('flagged').checked;
  if(!args.title){$('form-error').textContent='Enter a reminder title.';return;}
  const due=$('due').value;if(due&&(!editing||due!==localInput(editing.due_at))){args.due_at=new Date(due).toISOString();args.remind_at=args.due_at;}
  const name=editing?'update_reminder':'create_reminder';if(editing)args.reminder_id=editing.id;else args.list_id=$('list-choice').value;
  busy=true;$('save').disabled=true;$('delete').disabled=true;$('cancel').disabled=true;render();
  try{applyMutation(name,args,unpack(await call(name,args)));$('editor').close();}
  catch(error){if($('editor').open)$('form-error').textContent=error.message;else showError(error);}
  finally{busy=false;$('save').disabled=false;$('delete').disabled=false;$('cancel').disabled=false;render();}
}
$('refresh').innerHTML=svg('refresh');$('plus').innerHTML=svg('plus');$('search-icon').innerHTML=svg('search');
$('refresh').onclick=refresh;$('search').oninput=render;$('new').onclick=()=>openEditor();$('add-row').onclick=()=>openEditor();$('form').onsubmit=save;
$('cancel').onclick=()=>$('editor').close();$('editor').addEventListener('cancel',e=>{if(busy)e.preventDefault();});
$('show-completed').onclick=()=>{showCompleted=!showCompleted;render();if(showCompleted)loadHistory();};
$('delete').onclick=async()=>{if(!editing||busy||!confirm(`Delete "${editing.title}" from Apple Reminders?`))return;const reminderId=editing.id;$('editor').close();await mutate('delete_reminder',{reminder_id:reminderId});};
renderNavigation();
async function connect() {
  const local=document.querySelector('meta[name="local-bridge"]');
  if(local){
    call=async(name,args)=>{const response=await fetch('/api/call',{method:'POST',headers:{'Content-Type':'application/json','X-Reminders-Token':local.content},body:JSON.stringify({name,arguments:args})});if(!response.ok)throw new Error(`Connection failed (${response.status})`);return response.json();};
    await refresh();
  } else {
    app.ontoolresult=response=>{if(response.isError){try{unpack(response);}catch(error){showError(error);$('connection').textContent='Connection issue';}}else if(response.structuredContent?.lists&&response.structuredContent?.reminders&&typeof response.structuredContent.fetched_at==='string'){accept(response);loadPresentation();}};
    call=(name,args)=>app.callServerTool({name,arguments:args},{timeout:210000});await app.connect(undefined,{timeout:15000});
  }
}
connect().catch(error=>{showError(error);$('connection').textContent='Connection issue';});
