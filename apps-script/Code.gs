/** Fit&Lead API. Deploy as owner, access: Anyone. No candidate data in GET. */
const HEADERS_=['ID записи','Хеш доступа','ФИО','Создано','Начало','Дедлайн','Блок 1','Блок 2','Блок 3','Отзыв'];
function setup(){
 const p=PropertiesService.getScriptProperties();
 if(!p.getProperty('SPREADSHEET_ID')){
  const ss=SpreadsheetApp.create('Fit&Lead — база обучения');const s=ss.getSheets()[0];s.setName('Кандидаты');s.appendRow(HEADERS_);s.setFrozenRows(1);s.getRange(1,1,1,10).setBackground('#005856').setFontColor('#ffffff').setFontWeight('bold').setWrap(true);s.setColumnWidth(3,260);s.setColumnWidth(10,400);s.setColumnWidths(4,6,165);s.getRange('D:I').setNumberFormat('dd.MM.yyyy HH:mm');s.hideColumns(2);s.getRange('J:J').setWrap(true);ss.setSpreadsheetTimeZone('Europe/Moscow');
  p.setProperty('SPREADSHEET_ID',ss.getId());
 }
 console.log('База: https://docs.google.com/spreadsheets/d/'+p.getProperty('SPREADSHEET_ID')+'/edit');
}
function sha_(s){return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,String(s),Utilities.Charset.UTF_8).map(b=>('0'+((b+256)%256).toString(16)).slice(-2)).join('');}
function token_(){return Utilities.getUuid().replace(/-/g,'')+Utilities.getUuid().replace(/-/g,'');}
function equal_(a,b){if(typeof a!=='string'||typeof b!=='string')return false;let d=a.length^b.length;for(let i=0;i<Math.max(a.length,b.length);i++)d|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);return d===0;}
function fail_(message){throw new Error(message);}
function sheet_(){const id=PropertiesService.getScriptProperties().getProperty('SPREADSHEET_ID');if(!id)fail_('База ещё не настроена');return SpreadsheetApp.openById(id).getSheetByName('Кандидаты');}
function sec_(v){return v instanceof Date?v.getTime()/1000:(v?Number(v):null);}
function state_(r,token){const d={id:token||r[0],name:r[2],created:sec_(r[3]),start:sec_(r[4]),deadline:sec_(r[5]),b1:sec_(r[6]),b2:sec_(r[7]),b3:sec_(r[8]),feedback:r[9]||''};d.completed=[d.b1,d.b2,d.b3].filter(Boolean).length;d.progress=[0,33,67,100][d.completed];d.duration=(d.b3||Date.now()/1000)-d.start;d.status=d.b3?(d.b3<=d.deadline?'Завершено в срок':'Завершено с просрочкой'):(Date.now()/1000>d.deadline?'Дедлайн истёк, обучение не завершено':'В процессе');return d;}
function safeText_(s){return /^[=+\-@\t\r]/.test(s)?"'"+s:s;}
function doGet(){return ContentService.createTextOutput(JSON.stringify({ok:true,service:'Fit&Lead API'})).setMimeType(ContentService.MimeType.JSON);}
function doPost(e){let result;const lock=LockService.getScriptLock();try{
 if(!e||!e.postData||e.postData.contents.length>16000)fail_('Некорректный запрос');const q=JSON.parse(e.postData.contents);if(!lock.tryLock(15000))fail_('Сервер занят. Повторите запрос.');result=dispatch_(q);
 }catch(error){result={error:error.message&&/^[А-Яа-яЁё]/.test(error.message)?error.message:'Ошибка сервера. Повторите запрос позже.'};}finally{if(lock.hasLock())lock.releaseLock();}
 return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}
function dispatch_(q){
 const action=q.action,data=q.data||{},token=String(q.token||''),p=PropertiesService.getScriptProperties(),cache=CacheService.getScriptCache();
 if(action==='hr/login'){
  const salt=p.getProperty('HR_SALT'),hash=p.getProperty('HR_HASH');if(!salt||!hash)fail_('Вход HR ещё не настроен');
  const key='login:'+Math.floor(Date.now()/60000),count=Number(cache.get(key)||0);if(count>=30)fail_('Слишком много попыток. Повторите через минуту.');
  if(!equal_(sha_(salt+String(data.password||'')),hash)){cache.put(key,String(count+1),70);fail_('Неверный пароль');}
  const t=token_();cache.put('hr:'+sha_(t),'1',21600);return {ok:true,token:t};
 }
 if(action==='hr/logout'){cache.remove('hr:'+sha_(token));return {ok:true};}
 if(action==='hr'||action==='export'){
  if(!token||cache.get('hr:'+sha_(token))!=='1')fail_('Войдите в HR-панель');
  const s=sheet_(),rows=s.getLastRow()>1?s.getRange(2,1,s.getLastRow()-1,10).getValues():[],candidates=rows.map(r=>state_(r));
  if(action==='hr')return {candidates};
  const lines=[['ФИО','Статус','Прогресс','Начало','Дедлайн','Блок 1','Блок 2','Блок 3 / завершение','Длительность, ч','Отзыв']];
  candidates.forEach(r=>lines.push([r.name,r.status,r.progress,...['start','deadline','b1','b2','b3'].map(k=>r[k]?new Date(r[k]*1000).toISOString():''),(r.duration/3600).toFixed(2),r.feedback]));
  return {csv:lines.map(row=>row.map(v=>'"'+safeText_(String(v)).replace(/"/g,'""')+'"').join(',')).join('\r\n')};
 }
 const s=sheet_(),rows=s.getLastRow()>1?s.getRange(2,1,s.getLastRow()-1,10).getValues():[];
 let access=action==='restore'?String(data.code||'').trim():token;
 if(action==='start'&&!access)access=String(data.requestId||'');
 let index=access?rows.findIndex(r=>equal_(r[1],sha_(access))):-1;
 if(action==='start'){
  if(index>=0)return {candidate:state_(rows[index],access)};
  const name=String(data.name||'').trim().replace(/\s+/g,' ');if(name.length<5||name.length>160||name.split(' ').length<2)fail_('Укажите фамилию и имя, при наличии — отчество');
  if(!/^[a-f0-9]{64}$/.test(access))fail_('Не удалось создать код сессии. Обновите страницу.');
  const now=new Date(),deadline=new Date(now.getTime()+259200000),row=[Utilities.getUuid(),sha_(access),safeText_(name),now,now,deadline,'','','',''];s.appendRow(row);SpreadsheetApp.flush();return {candidate:state_(row,access)};
 }
 if(action==='session')return {candidate:index>=0?state_(rows[index],access):null,serverTime:Date.now()/1000};
 if(index<0)fail_(action==='restore'?'Код восстановления не найден':'Сначала начните обучение');
 const r=rows[index],rowNumber=index+2;
 if(action==='restore')return {candidate:state_(r,access)};
 if(action==='complete'){
  const n=data.block;if(!Number.isInteger(n)||n<1||n>3)fail_('Некорректный блок');if(n>1&&!r[4+n])fail_('Сначала завершите предыдущий блок');if(data.confirmed!==true)fail_('Подтвердите просмотр видео');
  if(!r[5+n]){r[5+n]=new Date();s.getRange(rowNumber,6+n).setValue(r[5+n]);SpreadsheetApp.flush();}
  return {candidate:state_(r,access)};
 }
 if(action==='feedback'){
  if(!r[8])fail_('Сначала завершите обучение');const text=String(data.text||'').trim();if(!text||text.length>4000)fail_('Напишите отзыв до 4000 символов');s.getRange(rowNumber,10).setValue(safeText_(text));SpreadsheetApp.flush();return {ok:true};
 }
 fail_('Неизвестный запрос');
}
