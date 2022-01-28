import os
import re
import sys
import getopt
import xml.etree.ElementTree as ET
from typing import List, Dict, Tuple, Union, Optional
from species_link import insert_species_links


def bval(b: str) -> bool:
    '''
    Converts a string to boolean based on custom 'Truth'-words

    :param b: str to be made into a bool
    :returns: truth value of b
    '''
    return b.lower() in ['y', 'yes', 'true']

def get_input(message: str, input_type: str) -> Union[str, int, bool]:
    '''
    (str, str) -> str or int or bool
    Repeatedly prompts user for input, displaying message, and returning user input converted to type input_type

    :param message: message to display in input() prompt
    :param type: 's' -> str, 'i' -> int, 'b' -> bool
    :returns: valid input of type input_type
    '''
    input_type = input_type.lower()
    valid_input = False
    while not valid_input:
        user_input = input(message).strip('\n')

        if len(user_input) == 0:
            pass
        elif input_type == 's':
            valid_input = True
        elif input_type == 'i':
            try:
                user_input = int(user_input)
                valid_input = True
            except ValueError:
                print('Please enter an integer.\n')
            except Exception as ex:
                print(ex)
        elif input_type == 'b':
            user_input = bval(user_input)
            valid_input = True
    
    return user_input


def extract_journal_info(path: str) -> Tuple[str, str, str, str]:
	"""
	(str) -> (str, str, str, str)
	Returns the volume, number, year, and journal code for this particular
	journal by extracting info from the directory structure and file-naming
	conventions for Bioline tickets.

	:param path: filepath matching .*/\w\w\d+(\d+)/
	:returns: volume, number, year, and journal code for this issue
	"""

	# Filepath looks like .../.../jjVV(N)/
	folder = path[:-5]
	folder = folder[folder.rindex("/")+1:]

	# Pull out the journal code, volume, and issue
	inf_journal_code = folder[0:2].lower()
	inf_volume = folder[2:folder.index("(")]
	inf_number = folder[folder.index("(")+1:folder.index(")")]

	# Nest a level deeper and get the year
	for filename in os.listdir(path):
		# XML files are ALWAYS of the form JJYY###.xml
		year = filename[2:4]
		year = "19" + year if int(year) > 80 else "20" + year
		return (inf_volume, inf_number, year, inf_journal_code)

def save_config(journal_code, config: Dict[str, Union[str, bool, int]]) -> None:
	'''
	Writes a journal configuration out to a .config file

	:param journal_code: two-char journal code
    :param config: dict of config tokens to values
	'''
	config_f = open(f'./config/{journal_code}.config', 'w')
	for key in config.keys():
		config_f.write(key + '=' + str(config[key]) + '\n' * (0 if key == 'SPLITKEYWORDS' else 1))
	config_f.close()

def already_processed(elem):
    return not elem.attrib['id'] == journal_code + 'xxx'

def fix_redundant_page_numbers(elem):
    if re.match(r'(\d+)-\1$', elem.attrib['pages']):
        elem.attrib['pages'] = elem.attrib['pages'][:elem.attrib['pages'].index('-')]

def surround_headers(elem, front, intro_front, back):
    intro_headers = [
        r'background(:|\n)?', r'context(:|\n)?', r'introduction(:|\n)?', r'purpose(:|\n)?',
        r'case presentation(:|\n)'
    ]

    common_headers = [
        r'(materials|data) and methods?(:\n)?', r'data source &amp; methods?(:|\n)?', 
        r'results?(:|\n)?', r'conclusions?(:|\n)?', r'objectives?(:|\n)?', 
        r'discussions?(:|\n)?', r'antecedente(:|\n)', r'objetivos?(:|\n)?', 
        r'm&#233;todos(:|\n)?', r'resultados(:|\n)', r'objectif(:|\n)?',
        r'm&#233;thodologie(:|\n)', r'r&#233;sultats(:|\n)', r'conclusiones(:|\n)?',
    ]

    method_headers = [r'methods?(:|\n)?', r'methodology(:|\n)?']

    case_sensitive_common_headers = [r'Aims?(:|\n)', r'Findings?(:|\n)', r'FINDINGS?(:|\n)', 
        r'MAIN CONCLUSIONS?(:|\n)'
    ]

    # Apply formatting to intro headers
    for header in intro_headers:
        elem.text = re.sub(header, rf'{intro_front}\g<0>{back}', elem.text, flags=re.I)

    # Apply formatting to common and method headers
    for header in common_headers + method_headers:
        elem.text = re.sub(header, rf'{front}\g<0>{back}', elem.text, flags=re.I)

    # Apply formatting to case sensitive headers
    for header in case_sensitive_common_headers:
        elem.text = re.sub(header, rf'{front}\g<0>{back}', elem.text)


    # It's possible for some multi-word headers to get extra formatting
    elem.text = re.sub(r'<br/><b>(Materials and \n?<br/><b>Methods(:|\n)?)</b></b>', r'<br/><b>\g<1></b>', elem.text, flags=re.I)
        
def common_text_subs(elem):
	"""
	Formats words that predominantly require the processor to manually format 
	them with their most commonly formatted variant.

	:param text: text in which to replace unformatted words
	:returns: text with proper xml format tags applied
	"""
	
	txt_substitutions = {
		'H2O2': 'H<sub>2</sub>O<sub>2</sub>',
		'H2O': 'H<sub>2</sub>O',
		'H20': 'H<sub>2</sub>0',
		'H2SO4': 'H<sub>2</sub>SO<sub>4</sub>',
		'&lt;!--': '<!--',
		'--&gt;': '-->',
		'\\\'': '\''
	}

	# Store the regexes as single-item tuples (so they'll work in the loop)
	reg_substitutions = {
		# simple tags
		(r'&lt;(|/)(i|b|sup|sub)&gt;',): (r'<\1\2>',),
		# inverse units  
		(r'(m|g|ha| L|ml)-1',): (r'\1<sup>-1</sup>',),
		# scientific notation
		(r'(\d?\.?\d+ ?\n?(x|&#215;)\n? ?10)(-?\d+)',): (r'\1<sup>\3</sup>',),
		# extra whitespace in hyphenations
		(r'-\n ?',): (r'-',),
		# 50-doses
		(r'(LC|LD|IC)50',): (r'\1<sub>50</sub>',),
		# Bi-elemental oxygen compounds
		(r'([A-Z]|\d)O(\d)(\d?(\+|-|))',): (r'\1O<sub>\2</sub><sup>\3</sup>',),
		# metre-based units
		(r'/? ?(cm|km|m)(\d)',): (r'/\1<sup>\2</sup>',),
		# Ammonia-based compounds
		(r'NH(\d)(\+?)',): (r'NH<sub>\1</sub><sup>\2</sup>',),
	}

	# Replace all above simple text matches
	for key in txt_substitutions.keys():
		elem.text = elem.text.replace(key, txt_substitutions[key])

	# Replace all the above regex patterns
	for key in reg_substitutions.keys():
		elem.text = re.sub(key[0], reg_substitutions[key][0], elem.text, re.I)

	# Remove any empty tags (a few may be added during the above loops)
	elem.text = re.sub(r'<(i|b|sup|sub)><\/\1>', '', elem.text, re.I)

def write_problems_file(path: str, files: Dict[str, str]) -> None:
    """
    Generates problems file to be filled out by Proofer

    :param path: the path (including name) of the problems file
    :param files: a dict where keys are filenames of xml files for this issue. Values of dict are irrelevant
    :returns: None
    """
    file_body = "Proofed by: \n\n"
    for file in files.keys():
        file_body += file[:len(file)-4] + ":\n\n"

    f = open(path, "w")
    f.write(file_body)
    f.close()

def exists_discrepancies(d: Dict[str, str], expected: str) -> bool:
    '''
    Returns True if any keys of d map to a value other than expected, false otherwise
    
    :param d: dictionary to check
    :param expected: expected value for all keys of d
    :returns: True if at least one value in d != expected, false otherwise
    '''
    for key in d.keys():
        if d[key] != expected:
            return True
    return False

def print_discrepancy_report(d: Dict[str, str], disc_type: str) -> Dict[str, str]:
    '''
    Displays message to user listing all errors found of type disc_type and correction.
    Returns dictionary of problematic files
    '''

    print(f'Journal {disc_type} discrepancies:')
    # Todo: add error handling
    expected = {'volume':volume,'number':number,'year':year}[disc_type]

    problems = dict()
    for key in d.keys():
        if d[key] != expected:
            problems[key] = d[key]
    for key in problems.keys():
        print(f'  {key}: Expected {disc_type}="{expected}" but got {disc_type}="{problems[key]}" instead')

    return problems


def fix_discrepancies(files: Dict[str, str], directory_path: str, disc_type: str, expected: str) -> None:
    '''
    For each file in files, the incorrect attribute (disc_type) is updated with the correct value (expected)
    '''

    # Loop through each file that needs fixing
    for filename in files.keys():
        print(f'Fixing {filename}...')

        # Read in file contents
        tree = ET.parse(filepath + filename)
        article = tree.getroot()

        # Replace incorrect attribute with expected one in article tag
        article.set(disc_type, expected)

        # Index tag also needs to be updated
        index = root.find('index')
        index_tokens = index.text.split(' ')
        vn = index_tokens[2].split('N')
        if disc_type == 'volume':
            index_tokens[2] = f'V{expected}N{vn[1]}'
        elif disc_type == 'number':
            index_tokens[2] = f'{vn[0]}N{expected}'
        elif disc_type == 'year':
            index_tokens[0] = expected
        index.text = ' '.join(index_tokens)

        # If we're in debug mode, print lines to console. Otherwise save to file
        text = ET.tostring(root, encoding='unicode').replace(r'&lt;(/)?(i|b|sup|sub|br/)&gt;', '<\g<1>\g<2>>')
        if DEBUG:
            pass
        else:
            f = open(filepath + filename, 'w', encoding='utf-8')
            f.write(text)
            f.close()



########
# MAIN #
########

# Handle command line arguments
DEBUG = False
PATH = None

try:
    opts, args = getopt.getopt(sys.argv[1:], 'p:d', ['path=', 'debug'])
except getopt.GetoptError as e:
    print(e)
    exit(3)

for opt, arg in opts:
    if opt in ('-p', '--path'):
        PATH = arg.replace('\\', '/')
    elif opt in ('-d', '--debug'):
        DEBUG = True

# Get filepath of XML folder to process, and format appropriately
filepath = PATH
if (filepath == None):
    filepath = get_input('Enter path to xml folder to process: ', 's').replace('\\', '/')
if not filepath.endswith('/'):
    filepath += '/'

# Ensure path meets the pattern: .../jjv(n)/xml/
if not re.match(r'.*\/[a-z]{2}\d+\(.+\)\/xml\/$', filepath):
    print('Filepath Format Error (2): Filepath should end with /jjvv(n)/xml/')
    exit(2)

# Determine volume, year, issue, and number based on the path to the xml folder
(volume, number, year, journal_code) = extract_journal_info(filepath)


# Prep configurational variables
copyright = 'default'
text_subs = False
before_newline_count = 0
after_newline_count = 0
bold_headers = False
italic_headers = False
species_links = False
split_keywords = True

try:
    # Read in config data from appropriate config file if it exists, else prompt it from user
    config_f = open(f'./config/{journal_code}.config', 'r')
    print(f'Loading configuration for \'{journal_code}\'...')
    for line in config_f.readlines():
        tokens = [t.strip() for t in line.split('=')]
        if tokens[0] == 'COPYRIGHT':
            copyright = tokens[1]
        elif tokens[0] == 'TEXTSUBS':
            text_subs = bval(tokens[1])
        elif tokens[0] == 'NEWLINESBEFORE':
            before_newline_count = int(tokens[1])
        elif tokens[0] == 'NEWLINESAFTER':
            after_newline_count = int(tokens[1])
        elif tokens[0] == 'BOLD':
            bold_headers = bval(tokens[1])
        elif tokens[0] == 'ITALIC':
            italic_headers = bval(tokens[1])
        elif tokens[0] == 'SPECIESLINKS':
            species_links = bval(tokens[1])
        elif tokens[0] == 'SPLITKEYWORDS':
            split_keywords = bval(tokens[1])
        elif len(tokens[0]) > 0: #UNKNOWN TOKEN
            print(f'Unknown Token Error (1): Unknown token \'{tokens[0]}\' in file \'{journal_code}.config\'')
            exit(1)

except FileNotFoundError:
    # Manually retrieve config values from user
    copyright = get_input('Enter the journal copyright (or \"default\" if unsure): ', 's')
    text_subs = get_input('Auto-format common words? (y/n): ', 'b')
    add_newline = get_input('Add newlines before abstract section headers? (y/n): ', 'b')
    if (add_newline):
        before_newline_count = get_input('How many? ', 'i')
    add_newline = get_input('Add newlines after abstract section headers? (y/n): ', 'b')
    if (add_newline):
        after_newline_count = get_input('How many? ', 'i')
    bold_headers = get_input('Bold abstract headers? (y/n): ', 'b')
    italic_headers = get_input('Italic abstract headers? (y/n): ', 'b')
    species_links = get_input('Attempt to automatically insert species links? (y/n): ', 'b')
    split_keywords = get_input('Keywords uploaded as comma-delimited strings? (y/n): ', 'b')

    # Save configuration to file later reuse if desired
    save = get_input(f'Save this configuration for \'{journal_code}\'? (y/n): ', 'b')
    if save:
        save_config(journal_code, {
            'COPYRIGHT': copyright,
            'TEXTSUBS': text_subs,
            'NEWLINESBEFORE': before_newline_count,
            'NEWLINESAFTER': after_newline_count,
            'BOLD': bold_headers,
            'ITALIC': italic_headers,
            'SPECIESLINKS': species_links,
            'SPLITKEYWORDS': split_keywords
        })
        print('Configuration saved!\n')




# Define dictionaries to search later for metadata discrepancies
file_to_volume = dict()
file_to_number = dict()
file_to_year = dict()

# Loop through each XML file in the directory
print('Starting XML processing')
for filename in os.listdir(filepath):
    if filename.endswith('.xml'):
        # Parse XML into a tree and loop through all tags
        f = open(filepath + filename, 'r')
        root = ET.fromstring(f.read())
        f.close()

        for elem in root.iter():
            if elem.tag == 'article':
                # [ ] Check if this file has already been processed (skip if so)
                if already_processed(elem):
                    print('Already processed ' + filename + '...')
                    continue
                else:
                    print('Processing ' + filename)

                # [ ] Set ID
                elem.attrib['id'] = filename[0:-4]

                # [ ] Fix redundant page numbers, if possible
                fix_redundant_page_numbers(elem)

                # [ ] Add <article> attributes to discrepancy dictionaries
                file_to_volume[filename] = elem.attrib['volume']
                file_to_number[filename] = elem.attrib['number']
                file_to_year[filename] = elem.attrib['year']
            
            elif elem.tag == 'title':
                # [ ] Replace NA titles if applicable
                if re.match(r'^(N ?A ?|N ?/A ?|N ?\.A\.? ?)', elem.text, re.I):
                    elem.text = ''

                # [ ] Apply common textual substitutions to title
                if text_subs:
                    common_text_subs(elem)

            elif elem.tag == 'copyright':
                # [ ] Fill in copyright information
                if copyright.lower() == 'default':
                    elem.text = f'Copyright {year} - {elem.text}'
                else:
                    elem.text = f'Copyright {year} - {copyright}'

            elif elem.tag == 'keyword':
                # [ ] Remove superfluous commas from keywords
                elem.text = elem.text.replace(',;', ';')
                if split_keywords:
                    elem.text = elem.text.replace(',', ';')

            elif elem.tag == 'index':
                # [ ] Update id in the index tag
                elem.text = elem.text.replace(f'{journal_code}xxx', filename[:-4])

            elif elem.tag == 'abstract':
                # [ ] Add linebreaks, bolding, and italics to common headers
                if bold_headers and italic_headers:
                    surround_headers(elem, '<br/>' * before_newline_count + '<b><i>', '<b><i>', '</i></b>' + '<br/>' * after_newline_count)
                elif bold_headers:
                    surround_headers(elem, '<br/>' * before_newline_count + '<b>', '<b>', '</b>' + '<br/>' * after_newline_count)
                elif italic_headers:
                    surround_headers(elem, '<br/>' * before_newline_count + '<i>', '<i>', '</i>' + '<br/>' * after_newline_count)
                elif before_newline_count > 0 or after_newline_count > 0:
                    surround_headers(elem, '<br/>' * before_newline_count, '', '<br/>' * after_newline_count)

                # [ ] Apply common textual substitutions to abstract
                if text_subs:
                    common_text_subs(elem)

            elif elem.tag == 'author':
                # [ ] Remove NA author
                if re.match(r'^(N ?A ?|N ?/A ?|N ?\.A\.? ?)', elem.text, re.I):
                    elem.text = ''

            elif elem.tag == 'authors':
                # [ ] Remove NA authors
                for sub_elem in elem.iter():
                    if sub_elem.tag == 'lastname' and re.match(r'^(N ?A ?|N ?/A ?|N ?\.A\.? ?)', sub_elem.text, re.I):
                        sub_elem.text = ''


        # Insert species links if appropriate
        if species_links:
            insert_species_links(root)

        # If we're in debug mode, print lines to console. Otherwise save to file
        text = ET.tostring(root).decode('utf-8').replace(r'&lt;(/)?(i|b|sup|sub|br/)&gt;', '<\g<1>\g<2>>')
        if DEBUG:
            print(f'----------\n{text}\n----------')
        else:
            f = open(filepath + filename, 'w', encoding='utf-8')
            f.write(text)
            f.close()

print('Completed XML processing!\n')
print('Generating problems.txt...')
write_problems_file(f'{filepath}../{journal_code}{volume}({number}) Problems.txt', file_to_volume)
print('Proofing file generated!\n')
print('Running discrepancy analysis...')

# Fix any possible outliers in volume, number, and year if desired
confirmation = f"Would you like to automatically fix these problems? (y/n)"

if exists_discrepancies(file_to_volume, volume):
    problems = print_discrepancy_report(file_to_volume, 'volume')
    if get_input(confirmation, 'b'):
        fix_discrepancies(problems, filepath, 'volume', volume)

if exists_discrepancies(file_to_number, number):
    problems = print_discrepancy_report(file_to_number, 'number')
    if get_input(confirmation, 'b'):
        fix_discrepancies(problems, filepath, 'number', number)

if exists_discrepancies(file_to_year, year):
    problems = print_discrepancy_report(file_to_year, 'year')
    if get_input(confirmation, 'b'):
        fix_discrepancies(problems, filepath, 'year', year)


print("Done!")
