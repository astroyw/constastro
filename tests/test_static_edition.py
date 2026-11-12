import json
from pathlib import Path
import shutil
import subprocess
import unittest

from app.genetics import analyze,pedigree


def horse(ident,sex='M',sire=None,dam=None):
    return {'id':ident,'name':ident,'sex':sex,'sire_id':sire,'dam_id':dam}


@unittest.skipUnless(shutil.which('node'),'Node es opcional para verificar la edición estática.')
class StaticGeneticsParityTests(unittest.TestCase):
    def test_browser_wright_matches_python_including_inbred_parents_and_partial_trees(self):
        cases=[
            ([horse('a'),horse('b','H')],'a','b'),
            ([horse('f'),horse('m','H'),horse('s','M','f','m'),horse('d','H','f','m')],'s','d'),
            ([horse('f'),horse('m1','H'),horse('m2','H'),horse('s','M','f','m1'),horse('d','H','f','m2')],'s','d'),
            ([horse('f'),horse('m','H'),horse('s','M','f','m'),horse('d','H','f','m'),horse('inbred','M','s','d'),horse('fresh','H'),horse('child','H','inbred','fresh')],'inbred','child'),
            ([horse('f'),horse('s','M','f'),horse('d','H','f')],'s','d'),
        ]
        # A single founder at depth four on both sides yields 0.1953125%:
        # Python rounds that exact midpoint to the nearest even decimal.
        distant=[horse('founder')]
        for i in range(1,5):
            distant.append(horse(f's{i}','M','founder' if i==1 else f's{i-1}'))
            distant.append(horse(f'd{i}','H','founder' if i==1 else None,None if i==1 else f'd{i-1}'))
        cases.append((distant,'s4','d4'))
        script="""
import fs from 'node:fs';
const {analyze,pedigree}=await import('data:text/javascript;base64,'+fs.readFileSync('static/genetics.js').toString('base64'));
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(cases.map(([horses,sire,dam])=>({analysis:analyze(sire,dam,horses),tree:pedigree(sire,new Map(horses.map(h=>[h.id,h])))}))));
"""
        result=subprocess.run(['node','--input-type=module','-e',script],
                              input=json.dumps(cases),text=True,capture_output=True,check=True,cwd=Path(__file__).resolve().parents[1])
        actual=json.loads(result.stdout)
        for (horses,sire,dam),value in zip(cases,actual):
            self.assertEqual(value['analysis'],analyze(sire,dam,horses))
            self.assertEqual(value['tree'],pedigree(sire,{h['id']:h for h in horses}))

    def test_browser_rejects_cycles_missing_parents_and_invalid_crosses(self):
        cases=[([horse('a',sire='b'),horse('b',sire='a')],'a','b'),
               ([horse('a',sire='missing'),horse('b','H')],'a','b'),
               ([horse('a'),horse('b')],'a','b'),([horse('a')],'a','a')]
        script="""
import fs from 'node:fs';const {analyze}=await import('data:text/javascript;base64,'+fs.readFileSync('static/genetics.js').toString('base64'));
process.stdout.write(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(([horses,sire,dam])=>{
  try{analyze(sire,dam,horses);return null}catch(e){return e.message}
})));
"""
        result=subprocess.run(['node','--input-type=module','-e',script],
                              input=json.dumps(cases),text=True,capture_output=True,check=True,cwd=Path(__file__).resolve().parents[1])
        for case,message in zip(cases,json.loads(result.stdout)):
            with self.assertRaises(ValueError) as error:analyze(case[1],case[2],case[0])
            self.assertEqual(message,str(error.exception))
