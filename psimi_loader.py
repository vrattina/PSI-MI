#!/usr/bin/python3.6
#AUTHOR: RATTINA Vimel - 2020/02/14 - SIB & Enyo Pharma

import sys #I/O files
import os, errno #create folder
import requests #wget
import contextlib #close the url
import configparser #to load the configuration file
from io import StringIO #add a false header
import logging #log file
import pronto #load obo file
import codecs #write a file in UTF-8 and with \n \t
#from bs4 import BeautifulSoup #dependencies, to write in XML
from lxml import etree #dependencies, to write in XML
#from pprint import pprint

logging.basicConfig(format='%(asctime)s\t%(levelname)s\t%(message)s', level=logging.DEBUG)
logging.StreamHandler(sys.stdout)
logging.getLogger("requests").setLevel(logging.WARNING) #make silent requests.get prints
logging.getLogger("urllib3").setLevel(logging.WARNING)

##The aim of this script is to retrieve the latest psi-mi.obo file and parse it into a correct neXtProt XML syntax

## DEPENDENCIES: python 3.6, pronto, lxml and codecs (the latest is maybe pre-installed)

## INPUTS: ##
##-The 

## OUTPUTS: ##
##-Cre

###################
# FUNCTIONS #######
###################

### Function loading a property file to retrieve proxy and xml path
def config_output(property_file):
    config = configparser.ConfigParser()
    with open(property_file) as pf:
        pf = StringIO("[my_header]\n" + pf.read())
        config.readfp(pf)
        
        #config.get handle itself NoOptionError if variable does not exist
        cv_release = config.get("my_header", "cvterms.release")
        proxy_dir = config.get("my_header", "proxy.storage.dir")
        
        output_folder = proxy_dir+"/"+cv_release

        return output_folder


### Function to download the psi-mi obo file
def wget_obo_url(output_folder):
    obo_url = "http://ontologies.berkeleybop.org/mi.obo"
    obo_content = requests.get(obo_url, allow_redirects=True)
    output_folder += "/cv-psimi.proxied"

    try:
        obo_content.raise_for_status()
        encoded_obo = obo_content.text
        with codecs.open(output_folder, 'w', "utf-8-sig") as outputf:
            outputf.write(encoded_obo)
            outputf.write("\n") #add a last line otherwise problem during obo loading
            return output_folder

    except requests.exceptions.RequestException as e:
        logging.warning(obo_url+"\tdoes not exist")
        exit


def psimi_loader(property_file, step):

    logging.info("property file loading starts")
    output_folder = config_output(property_file)
    logging.info("property file loading ends")

    logging.info("psimi obo file downloading starts")
    obo_file = wget_obo_url(output_folder)
    logging.info("psimi obo file downloading ends")

    logging.info("obo file loading starts")
    mi = pronto.Ontology(obo_file)
    #mi = pronto.Ontology.from_obo_library("mi.obo") #can do it online also
    
    ont_keys = mi.keys()
    ont_vals = mi.values()
    ont_repr = mi.__repr__()
    ont_rel = mi.relationships()        
    #print("nb mi\t"+str(len(mi)))
    #print("nb terms\t"+str(len(ont_terms)))
    #print("nb relationships\t"+str(len(ont_rel)))

    ont_terms = mi.terms()

    with open("cv-psi-mi.xml", 'w') as outputf:

        root = etree.Element("object-stream")

        for method in ont_terms:

            m_obsolete = method.obsolete
            if m_obsolete == False:
                m_obsolete = "VALID"
            elif m_obsolete == True:
                continue #do not write if obsolete method

            #subclasses = mi[method.id].subclasses(with_self=False)
            #for i in subclasses:
            #    print (i)

            #parent_node = mi[method.id].is_leaf()
            #print (parent_node)

            cvtermwrapper_data = etree.SubElement(root, "com.genebio.nextprot.dataloader.cv.Cvtermwrapper_Data")
            psimi = etree.SubElement(cvtermwrapper_data, "termCategory")
            psimi.text = "PSI-MI"
            wrappedbean = etree.SubElement(cvtermwrapper_data, "wrappedBean")

            m_name = "![CDATA["+method.name+"]]"
            cvname = etree.SubElement(wrappedbean, "cvname")
            cvname.text = m_name

            m_def = "![CDATA["+method.definition+"]]"
            description = etree.SubElement(wrappedbean, "description")
            description.text = m_def
            
            status = etree.SubElement(wrappedbean, "status")
            status.text = m_obsolete

            dbxref = etree.SubElement(wrappedbean, "dbXref")
            resourcetype = etree.SubElement(dbxref, "resourceType")
            resourcetype.text = "DATABASE"

            m_id = "![CDATA["+method.id+"]]"
            accession = etree.SubElement(dbxref, "accession")
            accession.text = m_id

            cvdatabase = etree.SubElement(dbxref, "cvDatabase")
            cvname = etree.SubElement(cvdatabase, "cvName")
            cvname.text = "PSI_MI"

            ## cvTermSynonyms
            cvtermsynonyms = etree.SubElement(wrappedbean, "cvTermSynonyms")
            print("=======================\t"+method.id)
            synonym_frozenset = method.synonyms
            if ( len(synonym_frozenset) > 0):
                for synonym_obj in synonym_frozenset:
                    mystring = synonym_obj.__repr__()
                    description = mystring.split("',")[0].split("(")[1][1:]

                    ismain_bool = "true"
                    if "SynonymType" in mystring: #if empty ismain_bool = true also
                        alternate = mystring.split("SynonymType('")[1].split("'")[0]
                        if "alternate" in alternate:
                            ismain_bool = "false"

                    cvtermsynonym_data = etree.SubElement(cvtermsynonyms, "com.genebio.nextprot.datamodel.cv.CvTermSynonym")
                    synonymname = etree.SubElement(cvtermsynonym_data, "synonymName")
                    synonymname.text = description
                    synonymtype = etree.SubElement(cvtermsynonym_data, "synonymType")
                    synonymtype.text = "NAME" #only value found in nextprot xml files
                    ismain = etree.SubElement(cvtermsynonym_data, "isMain")
                    ismain.text = ismain_bool #true if not alternate
                    cvtermref = etree.SubElement(cvtermsynonym_data, "cvTerm", reference="../../..")
                    

            ## relationships
            relationships = etree.SubElement(cvtermwrapper_data, "relationships")
            
            relationship_frozendict = method.relationships
            for relationship in relationship_frozendict.items():
                if ( len(relationship) > 0 ):
                    typedef = relationship[0]
                    mi_name = relationship[1]
                    for i in mi_name:
                        mi_id = "![CDATA["+i.id+"]]"
                        #mi_name = i.name ##not needed
                        
                        relationship_data = etree.SubElement(relationships,"com.genebio.nextprot.dataloader.cv.Relationship")
                        relationship_elt = etree.SubElement(relationship_data, "relationship")

                        if ( typedef.name == "is a" ):
                            relationship_elt.text = "is_a"
                        elif ( typedef.name == "part of" ):
                            relationship_elt.text = "part_of"

                        accession  = etree.SubElement(relationship_data, "accession")
                        accession.text = mi_id
                        termcategory = etree.SubElement(relationship_data, "termCategory")
                        termcategory.text = "![CDATA[]]"
            
            #print (method.subsets) #also part_of Drugable and PSI-MI_slim

                        
            ## secondary ACs
            secondaryacs = etree.SubElement(cvtermwrapper_data, "secondaryAcs")

            secondaryac_frozenset = method.alternate_ids
            if ( len(secondaryac_frozenset) > 0):
                for secondaryac_obj in secondaryac_frozenset:
                    secondaryac = secondaryac_obj.__repr__()

                    string_ac = etree.SubElement(secondaryacs, "string")
                    string_ac.text = "![CDATA["+secondaryac+"]]"

            
            ## cv xrefs and dbxref 
            cvxrefs = etree.SubElement(cvtermwrapper_data, "cvXrefs")
            externaldbxrefs = etree.SubElement(cvtermwrapper_data, "externalDbXrefs")

            m_xref = method.definition.xrefs
            for xref in m_xref:
                db_ac_list = xref.id.split(":")
                db = db_ac_list[0]
                ac = db_ac_list[1]
                #print(db+"\t"+ac)
                
                if (db.upper() == "PUBMED" ):
                    externaldbxref_data = etree.SubElement(externaldbxrefs, "com.genebio.nextprot.dataloader.cv.CvXref")
                    accession = etree.SubElement(externaldbxref_data, "accession")
                    dbname = etree.SubElement(externaldbxref_data, "dbName")
                    accession.text = "![CDATA["+ac+"]]"
                    dbname.text = "PubMed"

                if (db.upper() == "DOI" ):
                    externaldbxref_data = etree.SubElement(externaldbxrefs, "com.genebio.nextprot.dataloader.cv.CvXref")
                    accession = etree.SubElement(externaldbxref_data, "accession")
                    dbname = etree.SubElement(externaldbxref_data, "dbName")
                    accession.text = "![CDATA["+ac+"]]"
                    dbname.text = "DOI"

                if (db.upper() == "RESID" ):
                    externaldbxref_data = etree.SubElement(externaldbxrefs, "com.genebio.nextprot.dataloader.cv.CvXref")
                    accession = etree.SubElement(externaldbxref_data, "accession")
                    dbname = etree.SubElement(externaldbxref_data, "dbName")
                    accession.text = "![CDATA["+ac+"]]"
                    dbname.text = "RESID"

                if (db.upper() == "GO" ): #does not exist in dbxref but cvxref
                    cvxref_data = etree.SubElement(cvxrefs, "com.genebio.nextprot.dataloader.cv.CvXref")
                    accession = etree.SubElement(cvxref_data, "accession")
                    dbname = etree.SubElement(cvxref_data, "dbName")
                    accession.text = "![CDATA["+xref.id+"]]"
                    dbname.text = "GO"

                #if (db.upper() == "SO" ): #does not exist in more dbxref and cvxref
                #    print (method)
                #    accession.text = "![CDATA["+xref.id+"]]"
                #    dbname.text = "SO"

            #print("=======================\t"+method.id)

        xmlstr = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True).decode()
        outputf.write(xmlstr)

    logging.info("obo file loading ends")


####################
# MAIN #############
####################
#also can use if in use that etc
if len(sys.argv) < 3:
    sys.exit('Usage: %s <> <>\n<>: \n<>:' % sys.argv[0])

if __name__ == "__main__":        
    psimi_loader(sys.argv[1], sys.argv[2])
#./psimi_loader.py EXAMPLE.tsv 2019_01
