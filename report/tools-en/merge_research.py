"""Merge the research report (D:/downloads/report_latex_v3/report.tex, English) into thesis-en as Part II.

- Chapter 9  = research sections 1-3 (introduction, pipeline and where to improve it, system overview)
- Chapter 10 = research sections 4-5 (attribute index, multi-agent reasoning)
- Chapter 11 = research sections 6-9 (setup, results, ablations, tooling)
- Sections 10-11 (limitations, conclusion) -> sections/research/_limits.tex and _conclusion.tex, used by Chapter 12
- Appendix A = system prompts (prompts/ copied next to main.tex)
Labels of the research report are prefixed with r- so that they cannot clash with Part I; citation keys are mapped to ref.bib.
The text itself is copied verbatim; only headings, labels, citation keys and "this report" wording are adapted.
"""
import re
import shutil
from pathlib import Path

SRC = Path(r'D:/downloads/report_latex_v3')
DST = Path(r'D:/uni-studies/semester-253/capstone_project_new/report/thesis-en')
OUT = DST / 'sections' / 'research'
OUT.mkdir(parents=True, exist_ok=True)

tex = (SRC / 'report.tex').read_text(encoding='utf-8')
body = tex[tex.index(r'\section{Introduction}'):tex.index(r'\begin{thebibliography}')]

# --- labels and references: prefix every research label with r-
labels = set(re.findall(r'\\label\{((?:sec|tab|fig):[^}]+)\}', body))
def pref(m):
    kind, name = m.group(2).split(':', 1)
    return f'{m.group(1)}{{{kind}:r-{name}}}'
body = re.sub(r'(\\label|\\ref)\{((?:sec|tab|fig):[^}]+)\}',
              lambda m: pref(m) if m.group(2) in labels else m.group(0), body)

# --- citation keys -> ref.bib
CITE = {'zara': 'li2025zara', 'yolo11': 'jocher2024yolo11', 'bytetrack': 'zhang2022bytetrack',
        'clip': 'laion2022clipvith14', 'milvus': 'milvusdocs', 'qwen': 'qwen2024qwen25vl3b',
        'gemini': 'googledeepmind-geminiflashlite', 'market1501': 'zheng2015market1501',
        'market1501attr': 'lin2019market1501attr'}
body = re.sub(r'\\cite\{([^}]+)\}', lambda m: r'\cite{' + ','.join(CITE[k.strip()] for k in m.group(1).split(',')) + '}', body)

# --- wording: the research is now Part II of a larger report
for a, b in [('this report', 'this part'), ('This report', 'This part'),
             ('in this report', 'in this part'), ('the report calls', 'this part calls'),
             ('The ablation this report cannot do', 'The ablation this part cannot do')]:
    body = body.replace(a, b)

def cut(start, end=None):
    i = body.index(start)
    j = body.index(end) if end else len(body)
    return body[i:j]

S_INTRO = r'\section{Introduction}'
S_PIPE = r'\section{The pipeline, and where to improve it}'
S_OVER = r'\section{System overview}'
S_INDEX = r'\section{The attribute index}'
S_REASON = r'\section{Multi-agent semantic reasoning}'
S_SETUP = r'\section{Experimental setup}'
S_LIMITS = r'\section{Limitations and future work}'
S_CONCL = r'\section{Conclusion}'
S_APP = r'\appendix'

HEAD = '% !TEX root = ../../main.tex\n% Part II (Nguyen Huu Cuong) - merged verbatim from the research report (report_latex_v3), see MERGE_NOTES.md.\n'

ch9 = cut(S_INTRO, S_INDEX).replace(S_INTRO, r'\section{Motivation and Contributions}' + '\n' + r'\label{sec:r-intro}', 1)
ch9 = ch9.replace(S_PIPE, r'\section{The Pipeline, and Where to Improve It}', 1).replace(S_OVER, r'\section{System Overview}', 1)
(OUT / 'chapter9.tex').write_text(HEAD +
    '\\chapter{Semantic Reasoning: Motivation and Overview}\n\\label{chapter:r-overview}\n\n'
    '\\textit{This chapter opens Part~II, the research on the search block. It states the problem and the contributions, '
    'reads the person search pipeline as a template of replaceable blocks, argues for improving the search block with a '
    'reasoning layer inspired by ZARA, and fills each block with a concrete model.}\n\n' + ch9, encoding='utf-8')

ch10 = cut(S_INDEX, S_SETUP).replace(S_INDEX, r'\section{The Attribute Index}', 1).replace(S_REASON, r'\section{Multi-Agent Semantic Reasoning}', 1)
(OUT / 'chapter10.tex').write_text(HEAD +
    '\\chapter{Attribute Index and Multi-Agent Reasoning}\n\\label{chapter:r-reasoning}\n\n'
    '\\textit{This chapter describes the attribute index built offline with a vision-language model, and the multi-agent '
    'funnel that re-ranks the candidates of CLIP retrieval from that evidence.}\n\n' + ch10, encoding='utf-8')

ch11 = cut(S_SETUP, S_LIMITS)
for a, b in [(S_SETUP, r'\section{Experimental Setup}'), (r'\section{Results}', r'\section{Results}'),
             (r'\section{Ablations and design decisions}', r'\section{Ablations and Design Decisions}'),
             (r'\section{Evaluation tooling and reproducibility}', r'\section{Evaluation Tooling and Reproducibility}')]:
    ch11 = ch11.replace(a, b, 1)
(OUT / 'chapter11.tex').write_text(HEAD +
    '\\chapter{Experiments and Results}\n\\label{chapter:r-experiments}\n\n'
    '\\textit{This chapter presents the experimental setup on Market-1501, the results of the reasoning layer against the '
    'CLIP baseline with an analysis of what it rescues and what it loses, the ablations of its mechanisms, and the '
    'tooling that makes every number reproducible.}\n\n' + ch11, encoding='utf-8')

# Limitations and conclusion of Part II: kept as fragments for Chapter 12 (shared)
limits = cut(S_LIMITS, S_CONCL)
limits = limits.replace(S_LIMITS, '').replace('\\label{sec:r-limits}', '', 1).strip()
(OUT / '_limits.tex').write_text(HEAD + '% Used by Chapter 12, section 12.2 (Part II limitations).\n\\label{sec:r-limits}\n' + limits + '\n', encoding='utf-8')
concl = cut(S_CONCL, S_APP).replace(S_CONCL, '').strip()
(OUT / '_conclusion.tex').write_text(HEAD + '% Used by Chapter 12, section 12.1 (Part II results).\n' + concl + '\n', encoding='utf-8')

# Appendix: prompts
app = cut(S_APP)
app = app.replace(S_APP, '').replace(r'\section{System prompts}', r'\chapter{System Prompts of Part II}', 1)
app = app.replace(r'\subsection{', r'\section{')
(OUT / 'appendix-prompts.tex').write_text(HEAD + app.strip() + '\n', encoding='utf-8')
shutil.copytree(SRC / 'prompts', DST / 'prompts', dirs_exist_ok=True)
(DST / 'figures' / 'research').mkdir(parents=True, exist_ok=True)
for f in (SRC / 'figs').iterdir():
    shutil.copy2(f, DST / 'figures' / 'research' / f.name)

print('labels prefixed:', len(labels))
for f in sorted(OUT.iterdir()):
    print(f.name, len(f.read_text(encoding='utf-8').splitlines()), 'lines')
