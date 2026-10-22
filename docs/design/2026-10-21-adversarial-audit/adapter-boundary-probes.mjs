import assert from 'node:assert/strict';
import { __test__ } from '/exports/para-lipg-hpc/mdmanurung/mycelium-extra/opencode/index.js';
const base=process.argv[2];
assert.equal(await __test__.runGate({py:base+'/wait.sh',gate:'unused'},'tool',{},5),null);
assert.deepEqual(await __test__.runGate({py:base+'/exit.sh',gate:'unused'},'tool',{text:'x'.repeat(2*1024*1024)},1000),{});
console.log('2 adapter boundary assertions passed');
