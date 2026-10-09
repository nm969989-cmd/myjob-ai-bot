'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {searchPlan}=require('./src/search-plan');
const config=require('./src/config');
test('bounded search diversifies roles and covers every city-role pair once',()=>{
 const cities=['Chennai','Vellore','Hosur'],roles=['nurse','developer'];
 const full=searchPlan(cities,roles,100);
 assert.equal(full.length,6);assert.equal(new Set(full.map(x=>JSON.stringify(x))).size,6);
 assert.deepEqual(full.slice(0,2).map(x=>x.keyword),roles);
 assert.equal(searchPlan(cities,roles,2,2)[0].city,'Hosur');
 assert.deepEqual(searchPlan([],roles,4),[]);
 assert.deepEqual(searchPlan(cities,roles,2,6),full.slice(0,2));
});
test('expanded locations retain original priorities and district aliases',()=>{
 assert.deepEqual(config.CITIES.slice(0,4),config.PRIORITY_CITIES);
 assert.ok(config.CITIES.includes('Hosur'));assert.ok(config.CITIES.includes('Tenkasi'));
 assert.equal(config.canonicalCity('tuticorin'),'Thoothukudi');
 assert.equal(config.cityLocation('Pondicherry'),'Puducherry, India');
});
