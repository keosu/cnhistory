// Project label positions onto a single non-overlapping row. The year anchors
// remain proportional; pooled adjacent blocks share the horizontal displacement.
export function layoutLandmarks(items, width, minYear, maxYear, gap=6) {
  if(!items.length)return {markers:[],rows:0};
  const total=items.reduce((sum,item)=>sum+item.width,0);
  gap=Math.min(gap,Math.max(0,(width-total)/Math.max(1,items.length-1)));
  const scale=Math.min(1,width/total);
  const markers=[],blocks=[];
  let offset=0;
  for(const item of items){
    const size=item.width*scale;
    const x=(item.year-minYear)/(maxYear-minYear)*width;
    const index=markers.length;
    markers.push({...item,width:size,x,offset,row:0});
    blocks.push({start:index,end:index,sum:x-size/2-offset,count:1});
    while(blocks.length>1){
      const right=blocks.at(-1),left=blocks.at(-2);
      if(left.sum/left.count<=right.sum/right.count)break;
      blocks.splice(-2,2,{start:left.start,end:right.end,sum:left.sum+right.sum,count:left.count+right.count});
    }
    offset+=size+gap;
  }
  const slack=Math.max(0,width-offset+gap);
  for(const block of blocks){
    const shift=Math.min(slack,Math.max(0,block.sum/block.count));
    for(let i=block.start;i<=block.end;i++)markers[i].left=markers[i].offset+shift;
  }
  return {markers,rows:1};
}
