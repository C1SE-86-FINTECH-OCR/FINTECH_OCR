"""Bounded financial-cell recovery: no real API, database or sample-specific rules."""
import unittest
from decimal import Decimal
from unittest.mock import patch
from PIL import Image,ImageDraw
from app import extraction as x

class SpatialTotalTests(unittest.TestCase):
    def test_currency_requires_explicit_evidence_and_preserves_conflicts(self):
        self.assertEqual(x.currency_observation('Currency: USD'),{'state':'observed','code':'USD'})
        self.assertEqual(x.currency_observation('Currency: USD\nCurrency: VND')['state'],'conflicting')
        self.assertEqual(x.currency_observation('Total: $100')['state'],'not_observed')
    def setUp(self):
        self.image=Image.new('RGB',(1000,300),'white')
        draw=ImageDraw.Draw(self.image)
        for pos in (10,650,800,990):draw.line((pos,50,pos,200),fill='black',width=3)
        self.words=[(20,100,65,120,'Tổng'),(72,100,125,120,'thanh'),(130,100,180,120,'toán')]
    def test_total_uses_actual_last_cell_not_fixed_page_percentage(self):
        label=x._payable_label_words(self.words)
        bounds=x._total_cell_bounds(self.image,self.words,label)
        self.assertGreater(bounds[0],790);self.assertGreater(bounds[2],950)
        with patch.object(x,'_tesseract_word_boxes',return_value=self.words),patch.object(x.pytesseract,'image_to_string',side_effect=['1.250.000','1.250.000']):
            self.assertEqual(x._recover_total_from_image(self.image),Decimal('1250000'))
    def test_zero_is_observed_amount_not_missing(self):
        with patch.object(x,'_tesseract_word_boxes',return_value=self.words),patch.object(x.pytesseract,'image_to_string',side_effect=['0','0']):
            self.assertEqual(x._recover_total_from_image(self.image),Decimal('0'))
    def test_disagreement_and_multiple_values_stay_unknown(self):
        for literals in (['1.250.000','1.350.000']*2,['250.000 1.250.000']*4):
            with patch.object(x,'_tesseract_word_boxes',return_value=self.words),patch.object(x.pytesseract,'image_to_string',side_effect=literals):
                self.assertIsNone(x._recover_total_from_image(self.image))
    def test_payment_method_and_vat_rows_are_not_payable_labels(self):
        for text in ('Hình thức thanh toán','Tiền thuế GTGT','Total VAT amount','Tổng tiền hàng'):
            row=[(n*90,100,n*90+70,120,w) for n,w in enumerate(text.split())]
            self.assertEqual(x._payable_label_words(row),[])

if __name__=='__main__':unittest.main()
