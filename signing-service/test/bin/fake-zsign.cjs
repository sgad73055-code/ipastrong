#!/usr/bin/env node
const fs = require('fs');
const a = process.argv.slice(2);
const get = f => a[a.indexOf(f) + 1];
const pass = get('-p');
if (pass === 'WRONG') { console.error('invalid password'); process.exit(1); }
fs.writeFileSync(get('-o'), 'SIGNED:' + fs.readFileSync(get('-k')).length);
