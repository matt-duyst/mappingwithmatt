import json, os, sys, time, unittest, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
PAGE = ('<!doctype html><meta charset="utf-8"><body style="margin:0;font:17px serif">'
        '<p style="text-align:justify;width:600px"><span>Boeing.</span> <span>Measuring that carbon is the center of the science.</span></p>'
        '<p style="text-align:justify;width:600px"><a href="https://example.com/">SeekOps</a>, spun out of a laboratory, measures methane.</p>')


@unittest.skipUnless(os.environ.get('CHROME'), 'needs a headless Chrome; runs in the review workflow')
class WordsAcrossElements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from run import Chrome
        from gaps import MEASURE
        c = Chrome(os.environ['CHROME'], 9993, os.path.join(HERE, '.tmp', 'test-gaps'), 1200, 400, True)
        try:
            c.send('Page.enable'); c.send('Runtime.enable')
            c.send('Page.navigate', {'url': 'data:text/html,' + urllib.parse.quote(PAGE)}); time.sleep(1.0); c.pump(0.5)
            cls.rows = json.loads(c.js(MEASURE))
        finally: c.close()
        cls.text = ' | '.join(r['words'] for r in cls.rows)

    def test_a_sentence_split_across_two_spans_stays_two_words(self):
        self.assertTrue(any('Boeing. Measuring' in r['words'] for r in self.rows), self.text)
        self.assertNotIn('Boeing.Measuring', self.text)

    def test_a_link_and_the_punctuation_after_it_are_one_word(self):
        self.assertTrue(any('SeekOps, spun' in r['words'] for r in self.rows), self.text)


if __name__ == '__main__':
    unittest.main()
