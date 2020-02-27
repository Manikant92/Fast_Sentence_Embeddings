#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Author: Oliver Borchers <borchers@bwl.uni-mannheim.de>
# Copyright (C) 2020 Oliver Borchers
# Licensed under GNU General Public License v3.0

"""
Automated tests for checking the model.
"""

import logging
import unittest

from pathlib import Path

import numpy as np

from fse.models.pooling import MaxPooling, train_pooling_np
from fse.models.base_s2v import EPS

from gensim.models import Word2Vec, FastText

logger = logging.getLogger(__name__)

CORPUS = Path("fse/test/test_data/test_sentences.txt")
DIM = 5
W2V = Word2Vec(min_count=1, size=DIM)
with open(CORPUS, "r") as f:
    SENTENCES = [l.split() for i, l in enumerate(f)]
W2V.build_vocab(SENTENCES)
W2V.wv.vectors[:,] = np.arange(len(W2V.wv.vectors), dtype=np.float32)[:, None]

W2V_R = Word2Vec(min_count=1, size=DIM)
W2V_R.build_vocab(SENTENCES)

FT = FastText(min_count=1, size=DIM)
FT.build_vocab(SENTENCES)
FT.wv.vectors[:,] = np.arange(len(FT.wv.vectors), dtype=np.float32)[:, None]
FT.wv.vectors_vocab = FT.wv.vectors
FT.wv.vectors_ngrams[:,] = np.arange(len(FT.wv.vectors_ngrams), dtype=np.float32)[
    :, None
]

FT_R = FastText(min_count=1, size=DIM)
FT_R.build_vocab(SENTENCES)


class TestPoolingFunctions(unittest.TestCase):
    def setUp(self):
        self.sentences = [
            ["They", "admit"],
            ["So", "Apple", "bought", "buds"],
            ["go", "12345"],
            ["pull", "12345678910111213"],
            "this is a longer test sentence test longer sentences".split(),
        ]
        self.sentences = [(s, i) for i, s in enumerate(self.sentences)]
        self.model = MaxPooling(W2V)
        self.model.prep.prepare_vectors(
            sv=self.model.sv, total_sentences=len(self.sentences), update=False
        )
        self.model._pre_train_calls()

    def test_cython(self):
        from fse.models.pooling_inner import (
            FAST_VERSION,
            MAX_WORDS_IN_BATCH,
            MAX_NGRAMS_IN_BATCH,
            train_pooling_cy,
        )
        self.assertTrue(FAST_VERSION)
        self.assertTrue(callable(train_pooling_cy))
        self.assertEqual(10000, MAX_WORDS_IN_BATCH)
        self.assertEqual(40, MAX_NGRAMS_IN_BATCH)

    def test_check_parameter_sanity(self):
        se = MaxPooling(W2V)
        se.word_weights = np.full(20, 2.0, dtype=np.float32)
        with self.assertRaises(ValueError):
            se._check_parameter_sanity()

        se = MaxPooling(W2V, window_size=0)
        with self.assertRaises(ValueError):
            se._check_parameter_sanity()

    def test_train(self):
        self.assertEqual(
            (100, 1450), self.model.train([(s, i) for i, s in enumerate(SENTENCES)])
        )

    def test_do_train_job(self):
        self.model.prep.prepare_vectors(
            sv=self.model.sv, total_sentences=len(SENTENCES), update=True
        )
        mem = self.model._get_thread_working_mem()
        self.assertEqual(
            (100, 1450),
            self.model._do_train_job(
                [(s, i) for i, s in enumerate(SENTENCES)],
                target=self.model.sv.vectors,
                memory=mem,
            ),
        )
        self.assertEqual((105, DIM), self.model.sv.vectors.shape)

    def test_pooling_train_np_w2v(self):
        self.model.sv.vectors = np.zeros_like(self.model.sv.vectors, dtype=np.float32)
        mem = self.model._get_thread_working_mem()

        output = train_pooling_np(
            self.model, self.sentences, self.model.sv.vectors, mem
        )

        self.assertEqual((5, 14), output)
        self.assertTrue((241 == self.model.sv[0]).all())
        self.assertTrue((306 == self.model.sv[1]).all())
        self.assertTrue((self.model.wv.vocab["go"].index == self.model.sv[2]).all())

    def test_pool_train_cy_w2v(self):
        self.model.sv.vectors = np.zeros_like(self.model.sv.vectors, dtype=np.float32)
        mem = self.model._get_thread_working_mem()

        from fse.models.pooling_inner import train_pooling_cy
        
        output = train_pooling_cy(
            self.model, self.sentences, self.model.sv.vectors, mem
        )

        self.assertEqual((5, 14), output)
        self.assertTrue((241 == self.model.sv[0]).all())
        self.assertTrue((306 == self.model.sv[1]).all())
        self.assertTrue((self.model.wv.vocab["go"].index == self.model.sv[2]).all())
    
    def test_pool_cy_equal_np_w2v(self):
        m1 = MaxPooling(W2V)
        m1.prep.prepare_vectors(
            sv=m1.sv, total_sentences=len(self.sentences), update=False
        )
        m1._pre_train_calls()
        mem1 = m1._get_thread_working_mem()
        o1 = train_pooling_np(m1, self.sentences, m1.sv.vectors, mem1)

        m2 = MaxPooling(W2V)
        m2.prep.prepare_vectors(
            sv=m2.sv, total_sentences=len(self.sentences), update=False
        )
        m2._pre_train_calls()
        mem2 = m2._get_thread_working_mem()

        from fse.models.pooling_inner import train_pooling_cy

        o2 = train_pooling_cy(m2, self.sentences, m2.sv.vectors, mem2)

        self.assertEqual(o1, o2)
        self.assertTrue((m1.sv.vectors == m2.sv.vectors).all())
    
    def test_pool_cy_equal_np_w2v_random(self):
        w2v = Word2Vec(min_count=1, size=DIM)
        # Random initialization
        w2v.build_vocab(SENTENCES)

        m1 = MaxPooling(w2v)
        m1.prep.prepare_vectors(
            sv=m1.sv, total_sentences=len(self.sentences), update=False
        )
        m1._pre_train_calls()
        mem1 = m1._get_thread_working_mem()
        o1 = train_pooling_np(m1, self.sentences, m1.sv.vectors, mem1)

        m2 = MaxPooling(w2v)
        m2.prep.prepare_vectors(
            sv=m2.sv, total_sentences=len(self.sentences), update=False
        )
        m2._pre_train_calls()
        mem2 = m2._get_thread_working_mem()

        from fse.models.pooling_inner import train_pooling_cy

        o2 = train_pooling_cy(m2, self.sentences, m2.sv.vectors, mem2)

        self.assertTrue(np.allclose(m1.sv.vectors, m2.sv.vectors, atol=1e-6))
    
    def test_pool_train_np_ft(self):
        m = MaxPooling(FT)
        m.prep.prepare_vectors(
            sv=m.sv, total_sentences=len(self.sentences), update=False
        )
        m._pre_train_calls()
        mem = m._get_thread_working_mem()

        output = train_pooling_np(m, self.sentences, m.sv.vectors, mem)

        self.assertEqual((5, 19), output)
        self.assertTrue((241 == m.sv[0]).all())
        self.assertTrue(
            np.allclose(737413.9, m.sv[2])
        )
        self.assertTrue(
            np.allclose(1080970.2, m.sv[3])
        )

    def test_pool_train_cy_ft(self):
        m = MaxPooling(FT)
        m.prep.prepare_vectors(
            sv=m.sv, total_sentences=len(self.sentences), update=False
        )
        m._pre_train_calls()
        mem = m._get_thread_working_mem()

        from fse.models.pooling_inner import train_pooling_cy

        output = train_pooling_cy(m, self.sentences, m.sv.vectors, mem)

        self.assertEqual((5, 19), output)
        self.assertTrue((241 == m.sv[0]).all())
        self.assertTrue(
            np.allclose(737413.9, m.sv[2])
        )
        self.assertTrue(
            np.allclose(1080970.2, m.sv[3])
        )

    def test_cy_equal_np_ft_random(self):
        ft = FastText(size=20, min_count=1)
        ft.build_vocab(SENTENCES)

        m1 = MaxPooling(ft)
        m1.prep.prepare_vectors(
            sv=m1.sv, total_sentences=len(self.sentences), update=False
        )
        m1._pre_train_calls()

        from fse.models.pooling_inner import MAX_NGRAMS_IN_BATCH

        m1.batch_ngrams = MAX_NGRAMS_IN_BATCH
        mem1 = m1._get_thread_working_mem()
        o1 = train_pooling_np(m1, self.sentences[:2], m1.sv.vectors, mem1)

        m2 = MaxPooling(ft)
        m2.prep.prepare_vectors(
            sv=m2.sv, total_sentences=len(self.sentences), update=False
        )
        m2._pre_train_calls()
        mem2 = m2._get_thread_working_mem()

        from fse.models.pooling_inner import train_pooling_cy

        o2 = train_pooling_cy(m2, self.sentences[:2], m2.sv.vectors, mem2)

        self.assertEqual(o1, o2)
        self.assertTrue(np.allclose(m1.sv.vectors, m2.sv.vectors, atol=1e-6))

    def test_pooling_train_np_w2v_non_negative(self):
        mpool = MaxPooling(W2V_R)
        mpool.train(self.sentences)
        self.assertTrue((mpool.sv.vectors >= 0).all())

    def test_hier_pooling_train_np_w2v(self):
        self.model.sv.vectors = np.zeros_like(self.model.sv.vectors, dtype=np.float32)
        mem = self.model._get_thread_working_mem()

        self.model.hierarchical = True

        output = train_pooling_np(
            self.model, self.sentences, self.model.sv.vectors, mem
        )
        self.model.hierarchical = False

        self.assertEqual((5, 14), output)
        self.assertTrue((183 == self.model.sv[0]).all())
        self.assertTrue(np.allclose(self.model.sv[4], 245.66667))

    def test_hpooling_train_np_w2v_non_negative(self):
        mpool = MaxPooling(W2V_R, hierarchical=True)
        mpool.train(self.sentences)
        self.assertTrue((mpool.sv.vectors >= 0).all())

    def test_pooling_train_np_ft_non_negative(self):
        mpool = MaxPooling(FT_R)
        mpool.train(self.sentences)
        self.assertTrue((mpool.sv.vectors >= 0).all())

    def test_hier_pooling_train_np_ft(self):
        m = MaxPooling(FT)
        m.prep.prepare_vectors(
            sv=m.sv, total_sentences=len(self.sentences), update=False
        )
        m._pre_train_calls()
        mem = m._get_thread_working_mem()

        m.hierarchical = True

        output = train_pooling_np(m, self.sentences, m.sv.vectors, mem)

        self.assertEqual((5, 19), output)
        self.assertTrue((183 == m.sv[0]).all())
        self.assertTrue((737413.9 == m.sv[2]).all())
        self.assertTrue((1080970.2 == m.sv[3]).all())
        """
        Note to future self:
        Due to the size of the ngram vectors,
        an ngram at the last position of the senence 
        will always be the highest value.
        TODO: This unittest is thus a bit flawed. Maybe fix?
        """

    def test_hier_pooling_train_np_ft_non_negative(self):
        mpool = MaxPooling(FT_R, hierarchical=True)
        mpool.train(self.sentences)
        self.assertTrue((mpool.sv.vectors >= 0).all())


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s : %(levelname)s : %(message)s", level=logging.DEBUG
    )
    unittest.main()
