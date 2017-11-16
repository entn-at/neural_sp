#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Define evaluation method by Character Error Rate (CSJ corpus)."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import re
from tqdm import tqdm

from utils.io.labels.character import Idx2char
from utils.io.variable import np2var
from utils.evaluation.edit_distance import compute_cer


def do_eval_cer(model, model_type, dataset, label_type, data_size, beam_width,
                is_test=False, eval_batch_size=None, progressbar=False):
    """Evaluate trained model by Character Error Rate.
    Args:
        model: the model to evaluate
        model_type (string): ctc or attention
        dataset: An instance of a `Dataset' class
        label_type (string): kanji or kanji or kanji_divide or kana_divide
        data_size (string): fullset or subset
        beam_width: (int): the size of beam
        is_test (bool, optional): set to True when evaluating by the test set
        eval_batch_size (int, optional): the batch size when evaluating the model
        progressbar (bool, optional): if True, visualize the progressbar
    Returns:
        cer_mean (float): An average of CER
    """
    batch_size_original = dataset.batch_size

    # Reset data counter
    dataset.reset()

    # Set batch size in the evaluation
    if eval_batch_size is not None:
        dataset.batch_size = eval_batch_size

    if 'kanji' in label_type:
        vocab_file_path = '../metrics/vocab_files/' + \
            label_type + '_' + data_size + '.txt'
    elif 'kana' in label_type:
        vocab_file_path = '../metrics/vocab_files/' + label_type + '.txt'

    idx2char = Idx2char(vocab_file_path)

    cer_mean = 0
    if progressbar:
        pbar = tqdm(total=len(dataset))
    for data, is_new_epoch in dataset:

        # Create feed dictionary for next mini-batch
        if model_type in ['ctc', 'attention']:
            inputs, labels, inputs_seq_len, labels_seq_len, _ = data
        elif model_type in ['hierarchical_ctc', 'hierarchical_attention']:
            inputs, _, labels, inputs_seq_len, _, labels_seq_len, _ = data
        else:
            TypeError

        # Wrap by variable
        inputs = np2var(inputs, use_cuda=model.use_cuda, volatile=True)
        inputs_seq_len = np2var(
            inputs_seq_len, use_cuda=model.use_cuda, volatile=True, dtype='int')

        batch_size = inputs[0].size(0)

        # Decode
        if model_type == 'attention':
            labels_pred, _ = model.decode_infer(
                inputs[0], inputs_seq_len[0], beam_width=beam_width)
        elif model_type == 'ctc':
            logits, perm_indices = model(inputs[0], inputs_seq_len[0])
            labels_pred = model.decode(
                logits, inputs_seq_len[0][perm_indices], beam_width=beam_width)
            labels_pred -= 1
            # NOTE: index 0 is reserved for blank

        for i_batch in range(batch_size):

            # Convert from list of index to string
            if is_test:
                str_true = labels[0][i_batch][0]
                # NOTE: transcript is seperated by space('_')
            else:
                if model_type in ['ctc', 'hierarchical_ctc']:
                    str_true = idx2char(
                        labels[0][i_batch][:labels_seq_len[0][i_batch]])
                elif model_type in ['attention', 'hierarchical_attention']:
                    str_true = idx2char(
                        labels[0][i_batch][1:labels_seq_len[0][i_batch] - 1])
                    # NOTE: Exclude <SOS> and <EOS>
            str_pred = idx2char(labels_pred[i_batch]).split('>')[0]
            # NOTE: Trancate by the first <EOS>

            # Remove garbage labels
            str_true = re.sub(r'[_NZー・<>]+', '', str_true)
            str_pred = re.sub(r'[_NZー・<>]+', '', str_pred)

            # Compute CER
            cer_mean += compute_cer(ref=str_true,
                                    hyp=str_pred,
                                    normalize=True)

            if progressbar:
                pbar.update(1)

        if is_new_epoch:
            break

    cer_mean /= len(dataset)

    # Register original batch size
    if eval_batch_size is not None:
        dataset.batch_size = batch_size_original

    return cer_mean