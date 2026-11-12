import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from project_context import related,facts

class ProjectContextTests(unittest.TestCase):
 def test_relevant_question_and_followup_get_facts(self):
  history=[{'role':'user','content':'Cum funcționează lip-sync-ul în acest proiect?'},
   {'role':'assistant','content':'Prin viseme.'},{'role':'user','content':'Și pentru engleză?'}]
  self.assertTrue(related(history))
  self.assertIn('Three.js',facts('test-model','ro'))
  self.assertIn('test-model',facts('test-model','ro'))
 def test_greeting_and_generic_project_do_not_get_technical_context(self):
  for text in ['Bună seara!','Dă-mi o idee pentru un proiect de biologie.','Cât face 12 plus 15?']:
   self.assertFalse(related([{'role':'user','content':text}]))
 def test_old_project_topic_expires(self):
  history=[{'role':'user','content':'Cum funcționează Three.js?'}]+[{'role':'user','content':'Spune-mi despre plante.'}]*3
  self.assertFalse(related(history))
