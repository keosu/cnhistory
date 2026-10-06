import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {layoutLandmarks} from '../web/timeline-layout.js';

const navigation=JSON.parse(fs.readFileSync(new URL('../data/navigation.json',import.meta.url)));
const items=navigation.primary_periods.map(p=>({year:p.jump_year,width:Math.max(36,p.name.length*12+10)}));

test('landmark positions follow time rather than equal button spacing',()=>{
  const {markers}=layoutLandmarks(items,1000,-2000,2017);
  for(const marker of markers)assert.ok(Math.abs(marker.x-(marker.year+2000)/4017*1000)<1e-9);
  const qin=markers.find(m=>m.year===-221),han=markers.find(m=>m.year===-202);
  assert.ok(han.x-qin.x<5);
  assert.equal(qin.row,han.row);
  assert.ok(qin.left+qin.width<=han.left);
  assert.ok(qin.left+qin.width/2<qin.x && han.left+han.width/2>han.x);
});

for(const width of [280,342,720,1380])test(`all labels stay visible and do not overlap at ${width}px`,()=>{
  const {markers,rows}=layoutLandmarks(items,width,-2000,2017);
  assert.equal(markers.length,14);
  assert.equal(rows,1);
  for(const marker of markers){
    assert.ok(marker.left>=0&&marker.left+marker.width<=width+1e-9);
    for(const other of markers){
      if(marker===other||marker.row!==other.row)continue;
      assert.ok(marker.left+marker.width<=other.left+1e-9||other.left+other.width<=marker.left+1e-9);
    }
  }
});
