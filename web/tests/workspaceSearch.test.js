import test from 'node:test';
import assert from 'node:assert/strict';
import {rankingSearchResults,searchWorkspace} from '../src/workspaceSearch.js';
test('employee lookup ignores accents and preserves original team rank and completed count',()=>{
 const rows=[{user_id:1,full_name:'Phạm Thu Hà',completed:5},{user_id:2,full_name:'Trần Lan Hương',completed:3}];
 const found=rankingSearchResults(rows,'HUONG lan');
 assert.equal(found.length,1);assert.equal(found[0].metric,'3 completed trips');assert.equal(found[0].detail,'#2 in team ranking');assert.equal(found[0].path,'/ranking?period=all#ranking-2');
 assert.equal(rankingSearchResults(rows,'nhan vien di nhieu nhat')[0].title,'Phạm Thu Hà');
});
test('workspace search uses authorized endpoints and keeps permitted results if a source fails',async()=>{
 const calls=[];
 const result=await searchWorkspace(async path=>{calls.push(path);if(path.startsWith('/invoices?'))return [];if(path.startsWith('/ranking'))return [{user_id:2,full_name:'Trần Lan Hương',completed:3}];throw new Error('Unavailable')},'huong');
 assert.equal(result.rows[0].kind,'Ranking');assert.match(result.error,/Schedule: Unavailable/);assert.equal(calls.length,4);assert.ok(calls[0].includes('search=huong'));
});

test('employee profile is a separate search destination including trip statistics',async()=>{
 const result=await searchWorkspace(async path=>path.startsWith('/directory/profiles?')?[{id:7,full_name:'Lan Huong',completed_trips:2,rank:3}]:[],'huong');
 assert.equal(result.rows[0].kind,'Profiles');assert.equal(result.rows[0].path,'/people/7');assert.equal(result.rows[0].metric,'2 completed trips');
});
