#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Creates a html documentation for the model described
    in the TROLL input file.

    Usage :
        python modeldoc.py -i <troll_input_file.inp> -o <documentation_file.html> [-v]

"""

import getopt
import sys
import re
from datetime import datetime
from pyparsing import *
from jinja2 import Template


trollbnf = None


def troll_BNF():
    """
        This function defines a "grammar" - BNF (https://fr.wikipedia.org/wiki/Forme_de_Backus-Naur)
        to describe the equations in the input TROLL file
        See the documentation of the PyParsing module:
        http://pyparsing.wikispaces.com/
        And this guide:
        http://infohost.nmt.edu/tcc/help/pubs/pyparsing/web/index.html
        :return:
    """
    global trollbnf

    if not trollbnf:
        # We define language elements from bottom to top: first variables, then equations, then blocks...
        # variables: alphanumeric and dots and underlines, first character is not a number
        variable = Word(alphas+"_.", alphanums+"_.")

        # equations: "var_name: left part = right part,"
        nonequal = "".join([c for c in printables if c != "="]) + " \t\n"
        noncomma = "".join([c for c in printables if c != ","]) + " \t\n"
        equation = variable.setResultsName("name") + Literal(":").suppress() + \
                   Word(nonequal).setResultsName("left_side") + Literal("=").suppress() + \
                   Word(noncomma).setResultsName("right_side") + Optional(Literal(",")).suppress()

        # ADDEQ block: "ADDEQ TOP/BOTTOM, {equations};"
        block_addeq_begin = CaselessKeyword("ADDEQ") + \
                            Optional(CaselessKeyword("TOP") ^ CaselessKeyword("BOTTOM")) + ","
        block_end = ";"

        # Complete block of equations
        # The Group makes each equation is one separate list element in results
        equations = OneOrMore(Suppress(block_addeq_begin) +
                              OneOrMore(Group(equation)) + Suppress(block_end))

        # Find blocks in the file (suppress anything before the ADDEQ equations block)
        equations_blocks = OneOrMore(SkipTo(equations).suppress() + equations)

        # Finally, ignore comments in file
        trollbnf = equations_blocks.ignore(cppStyleComment)

    return trollbnf


def makeinternallinks(equations, verbose=False):
    """
    Make links on variables in equations, linking to equations anchors.
    Also make reverse links (in wich equations a variable appears ?)

    :param equations: list of equations = [name, left_side, right_side, whole_equation]
    :param verbose:
    :return: equations: list of equations = [name, left_side, right_side, whole_equation, variables, appears_in]
    """

    # Lower the case of the equations list
    # And also add the "variables" and the "appears in" list,
    equations = [{'name': eq['name'].lower(),
                  'left_side': eq['left_side'].lower(),
                  'right_side': eq['right_side'].lower(),
                  'whole_equation': eq['whole_equation'].lower(),
                  'variables': [],
                  'appears_in': []
                  } for eq in equations]

    # Extract the equations names
    names = [eq['name'] for eq in equations]
    # print(names)

    print("Linking: making html links on variables in equations...")
    for eq in equations:
        # Make links in right side of equations
        for name in names:
            # Perf improvements: don't perform unuseful regex searches
            if name in eq['whole_equation'] and name != eq['name']:
                # We replace occurences of variable names, but :
                # if "cd_ef" and "ab_cd_ef" exist as variables, we musn't replace the part "cd_ef" wich is in "ab_cd_ef"
                # So we use a regex with \b wich is a word boundary (eg non alpanumeric and non underscore character, or beginning/end of line).
                # If variable if found in equation, we complete the "variables" list, containing the list of the endogenous variables in the eq.

                regex = re.compile(r'\b(' + name + r')\b')
                if regex.search(eq['whole_equation']):
                    eq['variables'].append(name)
                    eq['whole_equation'] = regex.sub(r'<a href="#\1">\1</a>', eq['whole_equation'])
                    if verbose:
                        print("Making a link on " + name + " in " + eq['whole_equation'])

            if name == eq['name']:
                # also create a link, but add a special class
                p = re.compile(r'\b(' + name + r')\b')
                eq['whole_equation'] = p.sub(r'<a href="#\1" class="main_variable">\1</a>', eq['whole_equation'])

    print("Reverse linking: finding in which equations variables appear...")
    for eq in equations:
        for loop_eq in equations:
            if eq['name'] != loop_eq['name'] and eq['name'] in loop_eq['variables']:
                eq['appears_in'].append(loop_eq['name'])

    return equations


def generatehtml(equations, template, output):
    """
    Generate the html output, based on a Jinja template and the list of equations.

    :param equations: the list of equations.
    :param template: the Jinja html template.
    :param output: the html file.
    :return:
    """
    print("Generating html output...")

    with open(template) as f:
        tmpl = Template(f.read().decode('utf-8'))

    with open(output, "w") as output_file:
        output = tmpl.render(
            equations=equations,
            date=datetime.now().strftime('%d/%m/%Y à %H:%M').decode('utf-8')
        )

        # jinja returns unicode - so `output` needs to be encoded to a bytestring
        # before writing it to a file
        output_file.write(output.encode('utf-8'))


def usage():
    print("""
    Creates a html documentation for a model described in a TROLL input file.
    Usage :
        python modeldoc.py -i <troll_input_file.inp> -o <documentation_file.html> [-v]
        
        -i : troll input file (mandatory).
        -o : html output file (mandatory)
        -v : verbose, prints debug information   
    """)


def main():

    # Get and check program arguments
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:o:v", ["help", "input=", "output=", "verbose"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    input = None
    output = None
    verbose = False
    for o, a in opts:
        if o in ("-v", "--verbose"):
            verbose = True
        elif o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-i", "--input"):
            input = a
        elif o in ("-o", "--output"):
            output = a
        else:
            assert False, "unhandled option"
    if not input or not output:
        print("Missing argument")
        usage()
        sys.exit(2)

    # Parse input file for equations
    bnf = troll_BNF()
    equations = None
    try:
        print("Parsing input file for equations: " + input + " ...")
        equations = bnf.parseFile(input)
        # If parsing went fine, results contains a list of Dict indexed
        # by: variable, left_side, right_side
        if verbose:
            print('---')
            for equation in equations:
                # print(equation)
                print("Equation: " + equation['name'])
                print("Left side of equation: " + equation['left_side'])
                print("Right side of equation: " + equation['right_side'])
                print('---')
        print(str(len(equations)) + " equations found.")
    except ParseException as x:
        print("No equation found in file: " + input)
        sys.exit()

    # Reassemble left and right part into a unique string, because we don't really need
    # to separate the two parts
    for equation in equations:
        equation['whole_equation'] = equation['left_side'].strip() + " = " + equation['right_side'].strip()

    # Complete results with internal links from variables to equations
    equations = makeinternallinks(equations, verbose)

    # Generate the hml file
    generatehtml(equations, 'docindex.html.jinja', output)

    print("Done. Output in file " + output + ".")


main()