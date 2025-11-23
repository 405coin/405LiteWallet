#!/usr/bin/env python
 
                                       
                                      
 
                                                             
                                                                      
                                                                
                                                                      
                                                                      
                                                                   
                                      
 
                                                                
                                                                 
 
                                                                 
                                                                    
                                                       
                                                                     
                                                                    
                                                                   
                                                                  
           
import functools
import os
import string
from typing import Optional

import gettext

from .logging import get_logger


_logger = get_logger(__name__)
def _get_app_name():
    try:
        from . import constants
        return getattr(constants.net, "APP_NAME", "405 Lite Wallet")
    except Exception:
        return "405 Lite Wallet"

APP_NAME = _get_app_name()
LOCALE_DIR = os.path.join(os.path.dirname(__file__), 'locale', 'locale')


def _get_null_translations():
    """Returns a gettext Translations obj with translations explicitly disabled."""
    return gettext.translation('electrum', fallback=True, class_=gettext.NullTranslations)


                                                                              
                                                                       
_language = _get_null_translations()


def _ensure_translation_keeps_format_string_syntax_similar(translator):
    """This checks that the source string is syntactically similar to the translated string.
    If not, translations are rejected by falling back to the source string.
    """
    sf = string.Formatter()
    @functools.wraps(translator)
    def safe_translator(msg: str, **kwargs):
        translation = translator(msg, **kwargs)
        parsed1 = list(sf.parse(msg))                                                                          
        try:
            parsed2 = list(sf.parse(translation))
        except ValueError:                                          
            _logger.warning(
                f"rejected translation string: failed to parse. original={msg!r}. {translation=!r}",
                only_once=True)
            return msg
                                               
        if len(parsed1) != len(parsed2):
            _logger.warning(
                f"rejected translation string: num replacement fields mismatch. original={msg!r}. {translation=!r}",
                only_once=True)
            return msg
                                                                                    
        field_names1 = set(tupl[1] for tupl in parsed1)
        field_names2 = set(tupl[1] for tupl in parsed2)
        if field_names1 != field_names2:
            _logger.warning(
                f"rejected translation string: set of field_names mismatch. original={msg!r}. {translation=!r}",
                only_once=True)
            return msg
                      
        return translation
    return safe_translator


                                                                
                                                                                           
                                                                                         
                                                    
                                                                                      
                                                                                
                                                                                                       
                                                                                              
                                                                               
                                                                                                
                                                                         
                                                                                                               
                                                                                                                     
@_ensure_translation_keeps_format_string_syntax_similar
def _apply_branding(text: str) -> str:
    if not text:
        return text
    branded = text.replace("Electrum", APP_NAME)
    branded = branded.replace("electrum", APP_NAME.lower())
    branded = branded.replace("BTC", "405")
    branded = branded.replace("btc", "405")
    branded = branded.replace("Bitcoin", "405 Coin")
    branded = branded.replace("bitcoin", "405 coin")
    return branded


def _(msg: str, *, context=None) -> str:
    if msg == "":
        return ""                                                  
    if context:
        contexts = [context]
        if context[-1] != "|":                                        
            contexts.append(context + "|")
        else:
            contexts.append(context[:-1])
        for ctx in contexts:
            out = _language.pgettext(ctx, msg)
            if out != msg:                                 
                return _apply_branding(out)
                                  
    return _apply_branding(_language.gettext(msg))


def set_language(x: Optional[str]) -> None:
    _logger.info(f"setting language to {x!r}")
    global _language
    if not x:
        return
    if x.startswith("en_"):
                                                                        
                                                                 
        _language = _get_null_translations()
    else:
        _language = gettext.translation('electrum', LOCALE_DIR, fallback=True, languages=[x])


languages = {
    '': _('Default'),
    'ar_SA': _('Arabic'),
    'bg_BG': _('Bulgarian'),
    'cs_CZ': _('Czech'),
    'da_DK': _('Danish'),
    'de_DE': _('German'),
    'el_GR': _('Greek'),
    'eo_UY': _('Esperanto'),
    'en_UK': _('English'),                                                                    
    'es_ES': _('Spanish'),
    'fa_IR': _('Persian'),
    'fr_FR': _('French'),
    'hu_HU': _('Hungarian'),
    'hy_AM': _('Armenian'),
    'id_ID': _('Indonesian'),
    'it_IT': _('Italian'),
    'ja_JP': _('Japanese'),
    'ky_KG': _('Kyrgyz'),
    'lv_LV': _('Latvian'),
    'nb_NO': _('Norwegian Bokmal'),
    'nl_NL': _('Dutch'),
    'pl_PL': _('Polish'),
    'pt_BR': _('Portuguese (Brazil)'),
    'pt_PT': _('Portuguese'),
    'ro_RO': _('Romanian'),
    'ru_RU': _('Russian'),
    'sk_SK': _('Slovak'),
    'sl_SI': _('Slovenian'),
    'sv_SE': _('Swedish'),
    'ta_IN': _('Tamil'),
    'th_TH': _('Thai'),
    'tr_TR': _('Turkish'),
    'uk_UA': _('Ukrainian'),
    'vi_VN': _('Vietnamese'),
    'zh_CN': _('Chinese Simplified'),
    'zh_TW': _('Chinese Traditional')
}
assert '' in languages
