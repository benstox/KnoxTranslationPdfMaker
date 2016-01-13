#!/usr/bin/env python3

import re
import os
import sys
import requests
from bs4 import BeautifulSoup
import unicode_to_latex

URL_STEM = 'http://www.newadvent.org/bible/'
ORDINALS = {1: 'First', 2: 'Second', 3: 'Third', 4: 'Fourth', 5: 'Fifth'}
LANGUAGE_IDS = {'latin': 3, 'english': 2, 'greek': 1}
BOOKS = []

def number_to_roman(num):
    roman = ""
    #figure out the thousands first
    thousands = num // 1000
    for i in range(thousands):
        roman = roman + "m"
    num = num - thousands * 1000
    #figure out the hundreds
    hundreds = num // 100
    if hundreds == 9:
        roman = roman + "cm"
    elif hundreds >= 5:
        roman = roman + "d"
        for i in range(hundreds - 5):
            roman = roman + "c"
    elif hundreds == 4:
        roman = roman + "cd"
    else:
        for i in range(hundreds):
            roman = roman + "c"
    num = num - hundreds * 100
    #figure out the tens
    tens = num // 10
    if tens == 9:
        roman = roman + "xc"
    elif tens >= 5:
        roman = roman + "l"
        for i in range(tens - 5):
            roman = roman + "x"
    elif tens == 4:
        roman = roman + "xl"
    else:
        for i in range(tens):
            roman = roman + "x"
    num = num - tens * 10
    #figure out the ones
    if num == 9:
        roman = roman + "ix"
    elif num >= 5:
        roman = roman + "v"
        for i in range(num - 5):
            roman = roman + "i"
    elif num == 4:
        roman = roman + "iv"
    else:  
        for i in range(num):
            roman = roman + "i"
    return(roman)

def create_directory(dirname):
    "creates a new directory if it doesn't already exist"
    if not os.path.exists(dirname):
        os.makedirs(dirname)

def webpage_to_soup(url):
    "make a get request to a website, return a soup"
    r = requests.get(url)
    soup = BeautifulSoup(r.content)
    return(soup)
        
def read_in_latex_template(filename):
    "reads in a .tex file"
    with open(filename) as f:
        template = f.read()
    return(template)
    
def write_latex_output_to_file(output, filename):
    "write the new latex document with the bilingual text to a file"
    with open(filename + '.tex', 'w') as f:
        f.write(output)

class Book(object):
    def __init__(self, start_filename):
        self.start_filename = start_filename
        self.start_url = URL_STEM + self.start_filename
        self.start_soup = webpage_to_soup(self.start_url)
        self.number_of_chapters = self.get_number_of_chapters(self.start_soup)
        self.chapter_urls = self.get_chapter_urls()
        self.title = self.get_title_of_book(self.start_soup)
        self.dirname = self.title_to_dirname(self.title)
        self.chapters = []
        self.create_chapters()
        BOOKS.append(self)
    
    def create_chapters(self):
        for i in range(self.number_of_chapters):
            self.chapters.append(Chapter(self.chapter_urls['urls'][i],
                                         self.chapter_urls['filenames'][i],
                                         i+1,
                                         self.title,
                                         self.dirname))
        
    def get_number_of_chapters(self, soup):
        "get the number of chapters in this book"
        chapters = soup.find_all('a', class_='biblechapter')
        return(len(chapters) + 1)
        
    def get_chapter_urls(self):
        "get the urls of all the chapters in this book"
        chapter_urls = {'urls': [self.start_url], 'filenames': [self.start_filename]}
        chapters = self.start_soup.find_all('a', class_='biblechapter')
        chapter_urls['urls'] += list(map(lambda x: URL_STEM + x['href'][2:], chapters))
        chapter_urls['filenames'] += list(map(lambda x: x['href'][2:], chapters))
        return(chapter_urls)
    
    def get_title_of_book(self, soup):
        "get title of this book"
        h1s = soup.find_all('h1')
        title = re.sub('^(.*) [0-9]+$', '\\1', h1s[0].text)
        return(title)
        
    def title_to_dirname(self, title):
        "format a book title to a directory name, e.g. 1 Maccabees -> first_maccabees"
        title = re.sub(' ', '_', title)
        if re.search('^[0-9]+_', title):
            initial_numbers = re.findall('^[0-9]*', title)
            ord = ORDINALS[int(initial_numbers[0])]
            title = re.sub('^[0-9]*', ord, title)
        title = title.lower()
        return(title)

class Chapter(object):
    def __init__(self, url, filename, number, book_title, book_dirname, soup=None):
        self.url = url
        self.filename = filename
        self.number = number
        self.book_title = book_title
        self.book_dirname = book_dirname
        self.soup = soup
        
        if not self.soup:
            self.soup = webpage_to_soup(self.url)
        
        self.footnotes = self.get_footnotes_from_soup()
        self.latin_pars = self.get_text_from_soup()
        self.english_pars = self.get_text_from_soup(language='english')
            
    def get_text_from_soup(self, language='latin'):
        "grabs the paragraphs for one of the three languages"
        language_id = LANGUAGE_IDS[language]
        paragraphs = self.soup.find_all('td', class_='bibletd' + str(language_id))
        paragraphs = list(map(lambda x: x.text.strip(), paragraphs))
        paragraphs = list(map(lambda x: self.fix_spacing_around_verse_numbers(x), paragraphs))
        if self.number == 1:
            paragraphs = self.do_dropcaps(paragraphs, lines=3)
        else:
            paragraphs = self.do_dropcaps(paragraphs)
        paragraphs = list(map(lambda x: self.turn_verse_numbers_red(x), paragraphs))
        paragraphs = list(map(lambda x: self.latexify_certain_ones(x), paragraphs))
        paragraphs = list(map(lambda x: self.add_footnotes_to_text(x), paragraphs))
        #paragraphs = list(map(lambda x: self.latexify_everything(x), paragraphs))
        return(paragraphs)
        
    def add_footnotes_to_text(self, paragraph):
        if re.search('\[[0-9]+\]', paragraph):
            footnotes_found = list(set(re.findall('\[[0-9]+\]', paragraph)))
            for i in range(len(footnotes_found)):
                footnote_number = int(re.sub('[\[\]]', '', footnotes_found[i]))
                paragraph = re.sub('(\\' + footnotes_found[i][:-1] + '\])',
                                   '\\\\\\\\footnote\\1{' + re.sub('\[[0-9]+\] ', '', self.footnotes[footnote_number-1]) + '}',
                                   paragraph)
        return(paragraph)
            
    def get_footnotes_from_soup(self):
        "grabs the footnote text from the bottom of the page"
        footnote_ul = self.soup.find_all('ul', class_='bibleul')
        footnotes = footnote_ul[0].find_all('p')[:-1]
        footnotes = list(map(lambda x: x.text.strip(), footnotes))
        footnotes = list(map(lambda x: self.latexify_certain_ones(x, True), footnotes))
        return(footnotes)
        
    def fix_spacing_around_verse_numbers(self, paragraph):
        "e.g. the english text has \xa0 after verse numbers, the latin has a double space there"
        paragraph = re.sub('([0-9]+)  ', '\\1~', paragraph)
        paragraph = re.sub('\\xa0', '~', paragraph)
        paragraph = re.sub('  ', ' ', paragraph)
        return(paragraph)
        
    def turn_verse_numbers_red(self, paragraph):
        "turn all verse numbers red"
        paragraph = re.sub('([0-9]+)~', '\\\\\\\\textcolor{benred8}{\\1}~', paragraph)
        return(paragraph)
        
    def do_dropcaps(self, list_of_paragraphs, lines=2):
        "make the first letter of the chapter a big one"
        list_of_paragraphs[0] = re.sub('^1~([A-Za-z]{1})([A-Za-z]*) ',
                                       '\lettrine[lines=' + str(lines) + ']{\\1}{\\2} ',
                                       list_of_paragraphs[0])
        return(list_of_paragraphs)
        
    def latexify_everything(self, paragraph):
        for key, value in unicode_to_latex.unicode_to_latex.items():
            paragraph = re.sub(re.escape(key), re.escape(value), paragraph)
        return(paragraph)
                
    def latexify_certain_ones(self, paragraph, footnote=False):
        "so far: apostrophes, ellipses"
        if footnote:
            footnote_backslashes = '\\\\\\\\'
        else:
            footnote_backslashes = ''
        ones = {u'\u2019': unicode_to_latex.unicode_to_latex[u'\u0027'],
                u'\u2026': unicode_to_latex.unicode_to_latex[u'\u2026'].strip() + '\\\\ ',
                u'\u2018': unicode_to_latex.unicode_to_latex[u'\u0060']
        }
        for key, value in ones.items():
            paragraph = re.sub(key, footnote_backslashes + '\\\\\\' + value, paragraph)
        return(paragraph)
                
    def insert_into_template(self, template):
        "insert the latin and english paragraphs into a latex template"
        separator = '\n\\pend\\pstart\n'
        for i in range(len(self.latin_pars)):
            template = re.sub('(\\\\StartOfLatin\\n\\n)',
                              '\\1' + separator + self.latin_pars[-1-i],
                              template)
            template = re.sub('(\\\\StartOfEnglish\\n\\n)',
                              '\\1' + separator + self.english_pars[-1-i],
                              template)
        template = re.sub('(\\\\StartOfLatin\\n\\n)',
                          '\\1\\\\begin{large}\\\\begin{center}' + str(self.number) + '\end{center}\end{large}\n' ,
                          template)
        template = re.sub('(\\\\StartOfEnglish\\n\\n)',
                          '\\1\\\\begin{large}\\\\begin{center}' + str(self.number) + '\end{center}\end{large}\n' ,
                          template)
        return(template)
    
    def insert_just_english_into_template(self, template):
        "insert the latin and english paragraphs into a latex template"
        for i in range(len(self.english_pars)):
            template = re.sub('(\\\\chapter\*\{\}\\n\\n)',
                              '\\1' + self.english_pars[-1-i] + '\n',
                              template)
        template = re.sub('(\\\\chapter\*\{\}\\n\\n)',
                          '\\1\\\\begin{large}\\\\begin{center}\\\\textsc{Chapter ' + number_to_roman(self.number) + '}\end{center}\end{large}\n',
                          template)
        return(template)
    
    
    def soup_to_file(self):
        "save a webpage soup to file"
        create_directory(self.book_dirname)
        with open('./' + self.book_dirname + '/' + self.filename, 'w') as f:
             f.write(str(self.soup.encode('utf8')))



        
if __name__ == '__main__':    
    #Book('1ma001.htm')
    Book('1ch001.htm')
    
    template = read_in_latex_template('BookTemplate.tex')
    template_just_english = read_in_latex_template('BookTemplate_just_english.tex')
    
    output = template_just_english
    for i in range(len(BOOKS[0].chapters)):
        output = BOOKS[0].chapters[-1-i].insert_just_english_into_template(output)
    
    # add title of book
    output = re.sub('chapter\*\{', 'chapter*{' + BOOKS[0].title, output)
        
    write_latex_output_to_file(output, BOOKS[0].dirname)