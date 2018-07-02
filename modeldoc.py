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
import csv
from datetime import datetime
from pyparsing import *
from jinja2 import Environment, FileSystemLoader

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
        commentRegion = Suppress(CaselessLiteral("--region")) + Optional(restOfLine)
        commentEndRegion = Suppress(CaselessLiteral("--endregion")) + Optional(restOfLine)
        # Here, we should use ZeroOrMore for dealing with the void region of exchange rate, but it doesn't work yet :-(
        # So, I've just suppressed this void region at this stage
        region = Optional(commentRegion).setResultsName("name") + OneOrMore(Group(equation)).setResultsName("equations") + Suppress(Optional(commentEndRegion))
        regions = OneOrMore(Suppress(block_addeq_begin) +
                              OneOrMore(Group(region)) + Suppress(block_end))



        # Find blocks in the file (suppress anything before the ADDEQ equations block)
        regions_blocks = OneOrMore(SkipTo(regions).suppress() + regions )

        #superprintables = "".join([c for c in printables]) + "éèà \t"
        #comment = Literal("//")+Word(superprintables)+LineEnd()
        #comment = Literal("//") + (Optional(Literal("region"))|Optional(Literal("endregion"))).setResultsName("type") + Word(superprintables) + LineEnd()
        #comment = Literal("//") + Optional(restOfLine)
        #comments = OneOrMore(Group(comment))

        voidRegion = CaselessLiteral("--region") + Optional(restOfLine) + Optional(OneOrMore(cppStyleComment)) + CaselessLiteral(
            "--endregion") + Optional(restOfLine)
        comment = cppStyleComment|voidRegion

        # Finally, ignore comments in file
        #trollbnf = regions_blocks.ignore(cppStyleComment)
        trollbnf = regions_blocks.ignore(comment)
        #trollbnf = regions_blocks.ignore(comment)
        #comment.setParseAction(commentHandler)

    return trollbnf


def makeinternallinks(regions, verbose=False):
    """
    Make links on variables in equations, linking to equations anchors.
    Also make reverse links (in wich equations a variable appears ?)

    :param regions: list of regions of equations = [name, left_side, right_side, whole_equation]
    :param verbose:
    :return: regions: list of regions of equations = [name, left_side, right_side, whole_equation, variables, appears_in]
    """
    names = []
    for idx in range(len(regions)):
        # Lower the case of the equations list
        # And also add the "variables" and the "appears in" list,
        regions[idx].equations = [{'name': eq['name'].lower(),
                      'left_side': eq['left_side'].lower(),
                      'right_side': eq['right_side'].lower(),
                      'whole_equation': eq['whole_equation'].lower(),
                      'variables': [],
                      'appears_in': [],
                      } for eq in regions[idx].equations]

        # Extract the equations names
        names = names + [eq['name'] for eq in regions[idx].equations]
        # print(names)

    print("Linking: making html links on variables in equations...")
    for idx in range(len(regions)):
        for eq in regions[idx].equations:
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
    for idx in range(len(regions)):
        for eq in regions[idx].equations:
            for loop_idx in range(len(regions)):
                for loop_eq in regions[loop_idx].equations:
                    if eq['name'] != loop_eq['name'] and eq['name'] in loop_eq['variables']:
                        eq['appears_in'].append(loop_eq['name'])

    return regions

def replaceparamsbyvalues(regions, paramsfile, verbose=False):
    """
    Replace parameters of the equation by corresponding values

    :param regions: list of regions of equations = [name, left_side, right_side, whole_equation, variables, appears_in]
    :param paramsfile: file with parameter names and parameter values
    :param verbose:
    :return: equations: list of equations = [name, left_side, right_side, whole_equation, variables, appears_in]
    """
    params = {}
    with open(paramsfile, newline='', encoding='iso-8859-1') as csvfile:
        spamReader = csv.reader(csvfile, delimiter=';')
        for row in spamReader:
            #print(row[0], row[1])
            params[row[0].lower()] = row[1]
        #print(params)
    paramnames = list(params.keys())

    print("Replacing parameter names by their values...")
    for idx in range(len(regions)):
        for eq in regions[idx].equations:
            for paramname in paramnames:
                # Perf improvements: don't perform unuseful regex searches
                if paramname in eq['whole_equation']:
                    regex = re.compile(r'\b(' + paramname + r')\b')
                    if regex.search(eq['whole_equation']):
                        eq['whole_equation'] = regex.sub(eval('r'+repr(params[paramname])), eq['whole_equation'])
                        if verbose:
                            print("Replacing the parameter " + paramname + " in " + eq['whole_equation'])

    return regions

def insertlegends(regions, legendsfile, verbose=False):
    """
    Insert legends for each equation

    :param regions: list of regions of equations = [name, left_side, right_side, whole_equation, variables, appears_in]
    :param legendsfile: file with variables and their legends
    :param verbose:
    :return: regions: list of regions of equations = [name, left_side, right_side, whole_equation, variables, appears_in, legend]
    """

    # Add the "legend" field in equations
    for idx in range(len(regions)):
        regions[idx].equations = [{'name': eq['name'],
                                  'left_side': eq['left_side'],
                                  'right_side': eq['right_side'],
                                  'whole_equation': eq['whole_equation'],
                                  'variables': eq['variables'],
                                  'appears_in': eq['appears_in'],
                                  'legend': []
                                  } for eq in regions[idx].equations]

    legends = {}
    with open(legendsfile, newline='', encoding='iso-8859-1') as csvfile:
        spamReader = csv.reader(csvfile, delimiter=';')
        for row in spamReader:
            #print(row[0], row[1])
            legends[row[0].lower()] = row[1]
        #print(params)
    legendnames = list(legends.keys())

    print("Inserting legends...")
    for idx in range(len(regions)):
        for eq in regions[idx].equations:
            for legendname in legendnames:
                # Perf improvements: don't perform unuseful regex searches
                if legendname in eq['name']:
                    regex = re.compile(r'\b(' + legendname + r')\b')
                    if regex.search(eq['name']):
                        eq['legend'] = legends[legendname]
                        if verbose:
                            print("Inserting legend " + legendname + " corresponding to " + eq['name'])

    return regions

def generatehtml(regions, template, output):
    """
    Generate the html output, based on a Jinja template and the list of equations.

    :param regions: the list of regions of equations.
    :param template: the Jinja html template.
    :param output: the html file.
    :return:
    """
    print("Generating html output...")

    templateLoader = FileSystemLoader(searchpath="./")
    templateEnv = Environment(loader=templateLoader)
    tmpl = templateEnv.get_template(template)

    # Render template and write it to output file
    with open(output, "w", encoding='utf8') as output_file:
        output = tmpl.render(
            regions=regions,
            date=datetime.now().strftime('%d/%m/%Y - %Hh%M')
        )
        output_file.write(output)


def usage():
    print("""
    Creates a html documentation for a model described in a TROLL input file.
    Usage :
        python modeldoc.py -i <troll_input_file.inp> -p <param_file.csv> -l <legend_file.csv> -o <documentation_file.html> [-v]
        
        -i : troll input file (mandatory)
        -p : csv input file (mandatory)
        -l : csv legend file (mandatory)
        -o : html output file (mandatory)
        -v : verbose, prints debug information   
    """)


def main():

    # Get and check program arguments
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hi:p:l:o:v", ["help", "input=", "paramfile=", "legendfile=", "output=", "verbose"])
    except getopt.GetoptError as err:
        # print help information and exit:
        print(err)  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)
    input = None
    paramfile = None
    legendfile = None
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
        elif o in ("-p", "--paramfile"):
            paramfile = a
        elif o in ("-l", "--legendfile"):
            legendfile = a
        elif o in ("-o", "--output"):
            output = a
        else:
            assert False, "unhandled option"
    if not input or not paramfile or not legendfile or not output:
        print("Missing argument")
        usage()
        sys.exit(2)

    # Parse input file for equations
    bnf = troll_BNF()
    regions = None
    try:
        print("Parsing input file for equations: " + input + " ...")
        with open(input, "r", encoding='iso-8859-1') as input_file:
            # Formatting text by replacing region annotations "//region" and "//endregion" by "--region" and "--endregion"
            # for avoiding to suppress them with other comments
            input_text = input_file.read()
            regexRegion = re.compile(r'//region')
            regexEndRegion = re.compile(r'//endregion')
            formatted_text = regexRegion.sub(r'--region', input_text)
            print(formatted_text)
            formatted_text = regexEndRegion.sub(r'--endregion', formatted_text)

        with open('formatted_' + input, "w", encoding='iso-8859-1') as formatted_file:
            formatted_file.write(formatted_text)

        with open('formatted_' + input, "r", encoding='iso-8859-1') as formatted_file:
            regions = bnf.parseFile(formatted_file)
            if verbose:
                for line in regions:
                    print(line.name)
                    print(line.equations)

        # If parsing went fine, results contains a list of Dict indexed
        # by: variable, left_side, right_side
        nequations = 0
        if verbose:
            print('---')
            for region in regions:
                for equation in region.equations:
                    nequations = nequations + 1
                    # print(equation)
                    print("Equation: " + equation['name'])
                    print("Left side of equation: " + equation['left_side'])
                    print("Right side of equation: " + equation['right_side'])
                    print('---')
            print(str(nequations) + " equations found.")
    except ParseException as x:
        print("No equation found in file: " + input)
        sys.exit()

    # Reassemble left and right part into a unique string, because we don't really need
    # to separate the two parts
    for region in regions:
        for equation in region.equations:
            equation['whole_equation'] = equation['left_side'].strip() + " = " + equation['right_side'].strip()

    # Complete results with internal links from variables to equations
    regions = makeinternallinks(regions, verbose)

    # Replace parameters by their values
    regions = replaceparamsbyvalues(regions, paramfile, verbose)

    # Insert legends for each equation
    regions = insertlegends(regions, legendfile, verbose)

    # Generate the html file
    generatehtml(regions, 'docindex.html.jinja', output)

    print('Printing region names...')
    for line in regions:
        if len(str(line.name))>0:
            print(str(line.name)+'\n')
            #print(line.equations)

    print("Done. Output in file " + output + ".")

main()
