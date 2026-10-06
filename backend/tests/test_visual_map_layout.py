import unittest
from types import SimpleNamespace
from fastapi import HTTPException
from routers.map_management import validate_layout

class VisualMapValidationTests(unittest.TestCase):
    def body(self, **change):
        p={'id':'castle-1','name':'وینترفل','model':'winterfell','position':{'x':0,'y':.04,'z':0},'size':.1,'rotation':180,'lift':0}
        p.update(change)
        return SimpleNamespace(placements=[p],climate={'mode':'auto'})
    def test_valid_and_empty_layout(self):
        self.assertEqual(validate_layout(self.body())['placements'][0]['name'],'وینترفل')
        self.assertEqual(validate_layout(SimpleNamespace(placements=[],climate={}))['placements'],[])
    def test_rejects_invalid_geometry(self):
        for change in ({'size':float('nan')},{'lift':float('inf')},{'model':'bad'},{'position':{'x':9,'y':0,'z':0}}):
            with self.subTest(change=change), self.assertRaises(HTTPException):validate_layout(self.body(**change))
    def test_duplicate_id(self):
        body=self.body();body.placements*=2
        with self.assertRaises(HTTPException):validate_layout(body)
    def test_climate_probability(self):
        body=self.body();body.climate={'autumn_rain':1.2}
        with self.assertRaises(HTTPException):validate_layout(body)

if __name__=='__main__':unittest.main()
