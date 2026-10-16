# Kitten

An agentic Property Based Testing tool.

## Overview
This project aims to integrate LLM generated properties for use in Property Based Testing.

PBT is most effective with a substantial amount of properties for testing, but LLM generated properties may be contaminated by hallucinated properties and could cause false positive test failures. This project aims to add an element of agentic formalization to the generrated properties to ensure maximum accuracy. 

This project is a work in progress.


## Project Structure

This Project is designed to be a graph based state machine, and is implemented using LangGraph. The main state passes control to a extractor node, which splits a codebase into testable executables which are passed on to an LLM for property generation. 

Those properties will be formalized and tested with Hypothesis. Incorrect properties will see a loop back to the generation node, with notes on a fix.

The agentic element involves that loop, as well as allowing individual executables to be passed back for testing with suggested fixes. Only previously untested code will be tested again.

Where PBT is not the most optimal testing mechanism, a different method will be considered.

This project is a work in progess and specifics will be determined later.



## Getting Started
1. Clone the repository.

