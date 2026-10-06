import unittest
from routers.players import RegisterBody
class RegistrationTests(unittest.TestCase):
 def test_only_name_title_and_house_choices_required(self):
  body=RegisterBody(name='Arya',gender='lady',requested_castles=['Winterfell'])
  self.assertEqual(body.model_dump(),{'name':'Arya','gender':'lady','requested_castles':['Winterfell']})
 def test_registration_cannot_bypass_review_with_profile_upload(self):
  body=RegisterBody(name='Arya',gender='lady',requested_castles=['Winterfell'],backstory='unreviewed',profile_image='data:image/png;base64,test')
  self.assertNotIn('profile_image',body.model_dump());self.assertNotIn('backstory',body.model_dump())
