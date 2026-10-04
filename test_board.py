import unittest
import board
class Tests(unittest.TestCase):
 def test_missing_location_is_unclear(self): self.assertEqual(board.eligible('','Remote position')[0],'Unclear')
 def test_contradiction_is_not_confirmed(self): self.assertEqual(board.eligible('Worldwide','USA only',True)[0],'Excluded')
 def test_panama(self): self.assertEqual(board.eligible('Panama','')[0],'Confirmed')
 def test_timezone(self): self.assertEqual(board.eligible('Worldwide','',True,[1,2])[0],'Unclear')
 def test_source_dedup_and_status(self):
  a=board.row('Senior Software Engineer','Acme','Worldwide','','A','https://a.test/job')
  a['Status']='Applied'; a['First seen']='2026-01-01'
  b=board.row('Senior Software Engineer','Acme','Worldwide','','B','https://b.test/job')
  rows=board.merge([a],[b]);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['Status'],'Applied');self.assertEqual(rows[0]['First seen'],'2026-01-01')
 def test_timestamp_seconds_and_ms(self): self.assertEqual(board.date(1791125950),board.date(1791125950000))
 def test_tracking_url(self): self.assertEqual(board.canonical('https://a.test/job?utm_source=x&id=3'),'https://a.test/job?id=3')
if __name__=='__main__':unittest.main()
