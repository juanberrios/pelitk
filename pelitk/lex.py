import pickle
import re
import math
import random
import pkgutil
from pkg_resources import resource_filename

from nltk.corpus import wordnet
from scipy.optimize import curve_fit
import numpy as np

__version__ = '0.1'
__author__ = 'ELI Data Mining Group'

FILE_MAP = {
    'NGSL': resource_filename('pelitk', 'data/wordlists/ngsl_2k.txt'),
    'PET': resource_filename('pelitk', 'data/wordlists/pet_coca_2k.txt'),
    'PELIC': resource_filename('pelitk', 'data/wordlists/pelic_l3_2k.txt'),
    'SUPP': resource_filename('pelitk', 'data/wordlists/supplementary.txt')
}
# lookup table created from NGSL and spaCy word lists
LOOKUP = pickle.loads(pkgutil.get_data('pelitk', 'data/lemmatizer.pkl'))


def _load_wordlist(key):
    with open(FILE_MAP[key]) as f_in:
        wordlist = set([x.strip().lower() for x in f_in.readlines()])
    return wordlist


def lemmatize(tokens):
    """ Lemmatize with lookup table and return list of corresponding lemmas """
    return [LOOKUP.get(x, x) for x in tokens]


def re_tokenize(text):
    """
    Returns a list of tokens from input text
    Lowercase input, removing symbols and digits.
    """
    return re.findall(r"[A-Za-z]+", text.lower())


def adv_guiraud(text, freq_list='NGSL', custom_list=None,
                spellcheck=True, supplementary=True):
    """
    Calculates advanced guiraud: advanced types / sqrt(number of tokens)
    By default, uses NGSL top 2k words as frequency list
    custom_list is a custom list of common types for frequency list
    """

    if custom_list is not None:
        if not isinstance(custom_list, list):
            raise TypeError("Please specify a list of strings for custom_list")
        common_types = set(custom_list)
    else:
        if freq_list not in FILE_MAP:
            raise KeyError("""Please specify an appropriate frequency list with
                              custom_list or set freq_list to one of NGSL, PET,
                              PELIC.""")
        common_types = _load_wordlist(freq_list)
    if supplementary:
        common_types = common_types.union(_load_wordlist('SUPP'))
    if isinstance(text, str):
        tokens = re_tokenize(text)
    else:
        # already tokens?
        tokens = text

    if len(tokens) == 0:
        return 0

    advanced = set()
    for token in tokens:
        lemma = LOOKUP.get(token, token)
        if lemma not in common_types and (not spellcheck or wordnet.synsets(lemma)):
            advanced.add(lemma)

    return len(advanced)/math.sqrt(len(tokens))


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
    return D/N * (np.sqrt(1 + 2*N/D) - 1)


def vocd(text, spellcheck=True, length_range=(35, 50), num_subsamples=100, num_trials=3):
    """
    Calculate 'D' with voc-D method (approximation of HD-D)
    Inspired by
    https://metacpan.org/pod/release/AXANTHOS/Lingua-Diversity-0.07/lib/Lingua/Diversity/VOCD.pm
    """
    tokens = [x for x in re_tokenize(text) if not spellcheck or wordnet.synsets(LOOKUP.get(x, x))]
    if len(tokens) < length_range[1]:
        raise ValueError("""Sample size greater than population!. Either reduce
                            the bounds of length_range or try a different
                            text.""")
    total_d = 0
    for i in range(num_trials):
        # calculate a D value each trial and average them all
        ttr_list = []
        n_list = []
        for sample_size in range(length_range[0], length_range[1]+1):
            total_ttr = 0
            for j in range(num_subsamples):
                total_ttr += ttr(random.sample(tokens, sample_size))
            avg_ttr = total_ttr/num_subsamples
            ttr_list.append(avg_ttr)
            n_list.append(sample_size)
        D = _estimate_d(np.array(n_list), np.array(ttr_list))
        total_d += D
    avg_d = total_d/num_trials
    return avg_d


def ttr(tokens):
    """
    Calculate Type-Token Ratio
    """
    return len(set(tokens))/len(tokens)


def mtld(text, factor_size=0.72):
    """
    Implements the Measure of Textual Lexical Diversity (MTLD)
    """
    tokens = re_tokenize(text)
    forward_factor_count = _mtld_pass(tokens, factor_size)
    backward_factor_count = _mtld_pass(tokens[::-1], factor_size)
    mtld = (len(tokens)/forward_factor_count + len(tokens)/backward_factor_count)/2
    return mtld


def _mtld_pass(tokens, factor_size):
    """
    Helper function for mtld, computing one pass of mtld with given tokens.
    """
    current_idx = 0
    factor_count = 0
    for i in range(1, len(tokens)+1):
        this_slice = tokens[current_idx:i]
        if ttr(this_slice) < factor_size:
            factor_count += 1
            current_idx = i
    return factor_count


    


def maas(text):
    pass
