import pickle
import re
import math
import random
import pkgutil
from collections import Iterable
from pkg_resources import resource_filename

from nltk.corpus import wordnet
from scipy.optimize import curve_fit
import numpy as np

__version__ = '0.1'
__author__ = 'Pitt ELI Data Mining Group'

FILE_MAP = {
    'NGSL': resource_filename('pelitk', 'data/wordlists/ngsl_2k.txt'),
    'PSL3': resource_filename('pelitk', 'data/wordlists/psl3.txt'),
    'ENABLE1': resource_filename('pelitk', 'data/wordlists/enable1.txt'),
    'SUPP': resource_filename('pelitk', 'data/wordlists/supplementary.txt')
}

# lookup table created from NGSL and spaCy word lists
LOOKUP = pickle.loads(pkgutil.get_data('pelitk', 'data/lemmatizer.pkl'))


def _load_wordlist(key):
    with open(FILE_MAP[key]) as f_in:
        wordlist = set([x.strip().lower() for x in f_in.readlines()])
    return wordlist


def re_tokenize(text):
    """ regex tokenizer that lowercases input and removes symbols/digits.

    Args:
        text (str): An input string
    Returns:
        List of tokens found in input string
    """
    return re.findall(r"[A-Za-z]+", text.lower())


def spellcheck_filter(tokens):
    """ Remove tokens whose lemmas do not appear in wordnet.synsets()

    Args:
        tokens (List[str]): input list of tokens

    Returns:
        filtered list of tokens
    """
    return [t for t in tokens if wordnet.synsets(LOOKUP.get(t, t))]


def adv_guiraud(tokens,
                freq_list='NGSL',
                custom_list=None,
                spellcheck=True,
                supplementary=True,
                lemmas=False):
    """ Calculates advanced guiraud: advanced types / sqrt(number of tokens)

    By default, uses NGSL top 2k words as frequency list of common types to
    ignore.

    Args:
        tokens (str): Input string to calculate AG for
        freq_list (str): string specifying which freq list to use. Must be one
            of {'NGSL','PELIC', 'SUPP'}
        custom_list (List[str]): if not None, used as a list of
            common types to ignore for AG instead of freq_list.
        spellcheck (bool): boolean flag to ignore misspelled words
            checked via enable1 wordlist + 'i' + 'a'
        supplementary (bool): Include NGSL supplementary vocabulary in
            addition to specified frequency list
        lemmas (bool): whether to lemmatize before adding to advanced type count
    Returns:
        Calculated AG
    """

    if custom_list is not None:
        if not isinstance(custom_list, Iterable):
            raise TypeError("Please specify a list of strings for custom_list")
        common_types = set(custom_list)
    else:
        if freq_list not in FILE_MAP:
            raise KeyError("Please specify set freq_list to one of {}".format(
                ", ".join(FILE_MAP.keys())))

        common_types = _load_wordlist(freq_list)
    # Include supplementary
    if supplementary:
        common_types = common_types.union(_load_wordlist('SUPP'))

    # TODO: can we use the same spellchecking everywhere?
    # here we use enable1, elsewhere we use wordnet.synsets()
    dictionary = _load_wordlist('ENABLE1')
    dictionary.add('i')
    dictionary.add('a')

    if not len(tokens):
        return 0

    advanced = set()
    for token in tokens:
        if not lemmas:
            lemma = LOOKUP.get(token, token)
        else:
            lemma = token
        if lemma not in common_types:
            if spellcheck:
                if lemma in dictionary:
                    advanced.add(lemma)
            else:
                advanced.add(lemma)

    return len(advanced) / math.sqrt(len(tokens))


def _estimate_d(N, TTR):
    """
    Finds value for D to fit to curve, minimizing squared error
    """
    # initial guess of 100 for D
    popt, _ = curve_fit(_vocd_eq, N, TTR, p0=[100])
    return popt[0]


def _vocd_eq(N, D):
    """
    Equation for approximating TTR as function of N and D as described at
    http://www.leeds.ac.uk/educol/documents/00001541.htm
    """
    return D / N * (np.sqrt(1 + 2 * N / D) - 1)


def vocd(tokens,
         spellcheck=False,
         length_range=(35, 50),
         num_subsamples=100,
         num_trials=3):
    """
    Calculate 'D' with voc-D method (approximation of HD-D)
    Inspired by
    https://metacpan.org/pod/release/AXANTHOS/Lingua-Diversity-0.07/lib/Lingua/Diversity/VOCD.pm

    Args:
        tokens (list): input text string to compute voc-D measure for
        spellcheck (bool): if True, exclude words whose lemmas
            are not in nltk.wordnet.synsets
        length_range ((int, int)): tuple of the range of sample sizes
            to use in computing voc-D
        num_subsamples (int): number of subsamples to take per sample
            size
        num_trials (int): number of trials to average over

    Returns:
        avg_D (float): estimated D value
    """
    if spellcheck:
        tokens = spellcheck_filter(tokens)

    if len(tokens) < length_range[1]:
        raise ValueError("""Sample size greater than population!. Either reduce
                            the bounds of length_range or try a different
                            text.""")
    total_d = 0
    for i in range(num_trials):
        # calculate a D value each trial and average them all
        ttr_list = []
        n_list = []
        for sample_size in range(length_range[0], length_range[1] + 1):
            total_ttr = 0
            for j in range(num_subsamples):
                total_ttr += ttr(random.sample(tokens, sample_size))
            avg_ttr = total_ttr / num_subsamples
            ttr_list.append(avg_ttr)
            n_list.append(sample_size)
        D = _estimate_d(np.array(n_list), np.array(ttr_list))
        total_d += D
    avg_d = total_d / num_trials
    return avg_d


def ttr(tokens):
    """
    Calculate Type-Token Ratio (TTR)
    Args:
        tokens (List[str]): list of tokens
    Returns:
        TTR computed via num_unique_types / num_tokens
    """
    return len(set(tokens)) / len(tokens)


def mtld(tokens, spellcheck=False, factor_size=0.72):
    """
    Implements the Measure of Textual Lexical Diversity (MTLD)
    """
    if spellcheck:
        tokens = spellcheck_filter(tokens)

    forward_factor_count = _mtld_pass(tokens, factor_size)
    backward_factor_count = _mtld_pass(tokens[::-1], factor_size)
    if forward_factor_count == 0 or backward_factor_count == 0:
        raise ValueError("""Text ttr never fell below the specified
                            factor_size. Try increasing factor_size parameter
                            or using input with more repeated tokens. """)
    mtld = (len(tokens) / forward_factor_count +
            len(tokens) / backward_factor_count) / 2
    return mtld


def _mtld_pass(tokens, factor_size):
    """
    Helper function for mtld, computing one pass of mtld with given tokens.
    """
    current_idx = 0
    factor_count = 0
    for i in range(1, len(tokens) + 1):
        this_slice = tokens[current_idx:i]
        this_ttr = ttr(this_slice)
        if this_ttr < factor_size:
            factor_count += 1
            current_idx = i
    # account for remainder factor count
    if this_ttr > factor_size:
        factor_count += (1.0 - this_ttr) / (1.0 - factor_size)
    return factor_count


def maas(tokens, spellcheck=False):
    """
    Compute the a^2 Maas index.
    """
    if spellcheck:
        tokens = spellcheck_filter(tokens)
    num_tokens = len(tokens)
    num_types = len(set(tokens))
    a_squared = math.log(num_tokens) - \
        math.log(num_types) / math.log(num_tokens)**2
    return a_squared
