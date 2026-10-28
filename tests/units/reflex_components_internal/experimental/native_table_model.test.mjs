import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../../../../packages/reflex-components-internal/src/reflex_components_internal/experimental/nativeTableModel.js', import.meta.url), 'utf8');
const { deriveRows, validateTable } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const columns=[{key:'name'},{key:'amount',type:'number'}];
const rows=[{id:'a',name:'Project 10',amount:10},{id:'b',name:'Project 2',amount:2},{id:'c',name:'Other',amount:null},{id:'d',name:'Project 1',amount:2}];
test('numeric stable sorting keeps equal values and nulls last in both directions',()=>{
 assert.deepEqual(deriveRows(rows,columns,'',{key:'amount',direction:'asc'}).map(x=>x.id),['b','d','a','c']);
 assert.deepEqual(deriveRows(rows,columns,'',{key:'amount',direction:'desc'}).map(x=>x.id),['a','b','d','c']);
 assert.deepEqual(rows.map(x=>x.id),['a','b','c','d']);
});
test('case insensitive query and natural text sort preserve raw records',()=>{
 const result=deriveRows(rows,columns,' PROJECT ',{key:'name',direction:'asc'});
 assert.deepEqual(result.map(x=>x.id),['d','b','a']);assert.equal(result[0],rows[3]);
});
test('empty query/no sort returns source; unknown sort is harmless',()=>{
 assert.equal(deriveRows(rows,columns,'',null),rows);assert.equal(deriveRows(rows,columns,'',{key:'missing',direction:'asc'}),rows);
});
test('IDs reject missing duplicates numeric/string collisions and NaN',()=>{
 validateTable(rows,columns,'id');
 for(const invalid of [[{id:null}],[{id:NaN}],[{id:''}],[{id:'a'},{id:'a'}],[{id:1},{id:'1'}]]) assert.throws(()=>validateTable(invalid,columns,'id'),/IDs/);
 assert.throws(()=>validateTable(rows,[{key:'a'},{key:'a'}],'id'),/Columns/);
});
test('authored widths stay finite in supported range and prototype field names remain valid',()=>{
 validateTable([{id:'a',constructor:'alpha'}],[{key:'constructor',width:180},{key:'__proto__',width:100}],'id');
 for(const width of [NaN,Infinity,-1,0,89,481,'180']) assert.throws(()=>validateTable(rows,[{key:'name',width}],'id'),/width/);
});
test('missing prototype-named fields are empty rather than inherited objects',()=>{
 assert.deepEqual(deriveRows([{id:'a'}],[{key:'constructor'}],'function',null),[]);
});
