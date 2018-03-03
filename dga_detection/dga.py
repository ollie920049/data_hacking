import os
import pickle
import collections
import tldextract
import math
import numpy as np


class DGA:

    def __init__(self):
        clf = self._load_model_from_disk('dga_model_random_forest')
        alexa_vc = self._load_model_from_disk('dga_model_alexa_vectorizor')
        alexa_counts = self._load_model_from_disk('dga_model_alexa_counts')
        dict_vc = self._load_model_from_disk('dga_model_dict_vectorizor')
        dict_counts = self._load_model_from_disk('dga_model_dict_counts')
        self.model = {'clf': clf, 'alexa_vc': alexa_vc,
                      'alexa_counts': alexa_counts, 'dict_vc': dict_vc,
                      'dict_counts': dict_counts}

    @staticmethod
    def _domain_extract(url):
        ext = tldextract.extract(url)
        return ext.domain

    @staticmethod
    def _entropy(s):
        p, ln = collections.Counter(s), float(len(s))
        e = -sum(count / ln * math.log(count / ln, 2) for count in p.values())
        return e

    def evaluate_url(self, url):
        domain = self._domain_extract(url)
        alexa_match = self.model['alexa_counts'] * self.model['alexa_vc'].transform([url]).T
        dict_match = self.model['dict_counts'] * self.model['dict_vc'].transform([url]).T

        # Assemble feature matrix (for just one domain)
        X = np.array([len(domain), self._entropy(domain), alexa_match, dict_match]).reshape(1, -1)
        y_pred = self.model['clf'].predict(X)[0]
        return y_pred

    @staticmethod
    def _load_model_from_disk(name, model_dir='models'):
        model_path = os.path.join(model_dir, name + '.model')

        try:
            model = pickle.loads(open(model_path, 'rb').read())
        except Exception:
            return None
        return model


if __name__ == "__main__":
    dga = DGA()
    dga.evaluate_url('www.google.com')
    dga.evaluate_url('www.facebook.com')
    dga.evaluate_url('www.1cb8a5f36f.com')
