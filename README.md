# Bioline Processor
The *Bioline Processor* performs a preprocessing of XML files used to display abstracts at [Bioline International](http://www.bioline.org.br/). It fills in information that would previously have to be manually entered by an employee while simultaneously correcting common errors from the submission process. 

This script will also generate a journal `Problems.txt` file to be completed by an employee during the "proofing" stage.

## Usage
1. Open a terminal and navigate to the folder containing `process.py` (and all the other project files)
2. Type: `python process.py -p <PATH>` where `<PATH>` is the path to the folder containing XML files to be processed.   
If this is your first time processing an issue for a given journal, you will be prompted to input information to create a `.config` file that will be loaded the next time you process an issue from this journal
3. Follow any remaining on-screen prompts to correct errors found in the XML files (if any)
4. You're done!

## Command-Line Args
Arg | Description
--- | ---
`-d`, `--debug` | Turns on debug mode. Processed XML files will be printed to `stdout` instead of being overwritten
`-p <PATH>`, `--path <PATH>` | Specify the path to the XML folder containing files to be processed.

