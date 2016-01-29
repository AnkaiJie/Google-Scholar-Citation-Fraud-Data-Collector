'''
Created on Jan 05, 2016

@author: Ankai
'''
from bs4 import BeautifulSoup
from urllib.request import Request, urlopen
import requests
import lxml
import re
import PyPDF2
from _io import BytesIO


class Paper:
    def __init__ (self, link):
        self.__url = link
        self.__pdfUrl= None
        self.__pap_info = {}
        self.__citedByUrl = None
        self.__allAuthors = None 
        
        session = requests.session()
        response = session.get(self.__url)
        soup = BeautifulSoup(response.content, 'lxml')

        self.__pap_info['Title'] = soup.find('a', attrs={'class': 'gsc_title_link'}).text
        
        div_info_table = soup.find('div', attrs={'id':'gsc_table'})
        div_fields = div_info_table.find_all('div', attrs={'class':'gs_scl'})

        for field in div_fields:
            fieldName = field.find('div', attrs={'class':'gsc_field'}).text
            #don't need the description
            if (fieldName == "Description"):
                continue
            #stores both number of citations and link to citers page as a field
            if (fieldName == "Total citations"):
                citedBy = field.find('div', attrs={'style':'margin-bottom:1em'}).find('a')
                self.__pap_info['Citations'] = citedBy.text.replace("Cited by ", "")
                self.__citedByUrl = citedBy['href']
                break
            
            self.__pap_info[fieldName] = field.find('div', attrs={'class':'gsc_value'}).text


    def getUrl(self):
        return self.__url
    
    def getCitedByUrl(self):
        return self.__citedByUrl 
        
    def getInfo (self):
        return self.__pap_info

    def getPdfUrl(self):
        return self.__pdfUrl

    def findPdfUrlOnPage(self):
        extractor = GscPdfExtractor()
        return extractor.findPdfUrlFromInfo(self.__url)

    
    # returns a list of author objects - all the authors that collaborated on this paper
    def findAllAuthors(self):
        authors = self.pap_info['Authors']
        paperName = self.pap_info['Title']

        # taking out any special characters in paper name
        paperName = re.sub(r'\W+', ' ', paperName)
        paperName = "+".join(paperName.split())
        authors = authors.split(",")
        print (authors)
        authorList = []

        session = requests.session()
        
        # appends a new authors object as found from the name into the list
        for author in authors:
            authorFields = author.split()
            lastName = authorFields[len(authorFields)-1]
            
            #must get query into the right form as noted by GS link first+middle+last
            query = "+".join(authorFields)+"+"+paperName

            
            response = session.get('https://scholar.google.ca/scholar?q='+query+'&btnG=&hl=en&as_sdt=0%2C5')
            soup = BeautifulSoup(response.content, 'lxml')

            authorsData = soup.find('div', attrs={'class': 'gs_a'}).findAll('a')
            print (authorsData)
            
            foundAuthor = False
            for anAuthor in authorsData:
                if (anAuthor.text.find(lastName) !=-1):
                    link = anAuthor['href']
                    #default number of paper loads and corresponding paper objects stored for author is set to 1
                    thisAuthor = AcademicPublisher('https://scholar.google.ca' + link, 1)
                    authorList.append(thisAuthor)
                    foundAuthor = True
                    break;
                
            if(foundAuthor is False):
                print("cannot find author "+ author)
                authorList.append(lastName+" does not exist in GS database")
        
        # list of all authors of the paper (if they exist on google scholar) 
        # if they don't exist, they are stored as a string saying they don't exist
        return authorList

    '''#returns number of citations this paper makes to the specified author
    def getCitesToAuthor(self, last_name):
        p = PaperReferenceProcessor()
        p.getCitesToAuthor(last_name, p.getPdfContent(self.__pdfUrl))'''
    
        
class AcademicPublisher:

    def __init__ (self, mainUrl, numPapers):
        
        self.first_name = None
        self.last_name = None
        self.url = mainUrl        
        self.__paper_list = []
        
        session = requests.Session()
        response = session.get(self.url + '&cstart=0&pagesize=' + str(numPapers))
        soup = BeautifulSoup(response.content, "lxml")
       
        full_name = soup.find('div', attrs={'id': 'gsc_prf_in'}).text.lower().split()
        print(full_name)
        
        #stores the lowercase first and last names
        self.first_name=full_name[0]
        self.last_name=full_name[1]
        print(self.last_name)


        #appends all papers to paperlist
        for one_url in soup.findAll('a', attrs={'class':'gsc_a_at'}, href=True):
            #one_url['href'] finds the link to the paper page
            self.__paper_list.append(Paper('https://scholar.google.ca' + one_url['href']))
       
       
    def getPapers(self):
        #returns a list of Papers
        return self.__paper_list
    
    # returns number of times a paper that cited a paper from this author cited the author in total
    # takes the index of the paper in papers list and index of a citer in that paper object
    def getNumCitesByPaper(self, indexPaper, indexCiter):
        pdfExtractor = GscPdfExtractor()
        paper = self.__paper_list[indexPaper]
        pdfUrls = pdfExtractor.findPapersFromCitations(paper.getCitedByUrl())

        analyzer = PaperReferenceProcessor()
        content = analyzer.getPdfContent(pdfUrls[indexCiter])
        numCites = analyzer.getCitesToAuthor(self.getLastName(), content)

        return numCites

    def getFirstName(self):
        return self.first_name

    def getLastName(self):
        return self.last_name
    
class GscPdfExtractor:
    
    #returns the list of pdf urls from the first page of citations on Google Scholar
    def findPapersFromCitations(self, citationsUrl):
        session = requests.session()
        response = session.get(citationsUrl)
        soup = BeautifulSoup(response.content, 'lxml')
        
        linkExtracts = soup.findAll('div', attrs={'class':'gs_md_wp gs_ttss'})
        pdfUrls = []
        
        for extract in linkExtracts:
            #this code will skip links with [HTML] tag and throw error for links that are only "Get it at UWaterloo"
            try:
                if extract.find('span', attrs={'class':'gs_ctg2'}).text == "[PDF]":
                    pdfUrls.append(extract.find('a')['href'])
                else:
                    print(extract.find('span', attrs={'class':'gs_ctg2'}).text+" tag process will be coded later")
            except:
                print('No tag, "Get it at waterloo" part.. to be coded later')
            
        return pdfUrls

    #getting PDF url from paper info page, different from citation list page
    def findPdfUrlFromInfo(self, infoPageUrl):

        session = requests.session()
        response = session.get(infoPageUrl)
        soup = BeautifulSoup(response.content, 'lxml')

        linkExtracts = soup.findAll('div', attrs={'class':'gsc_title_ggi'})

        for extract in linkExtracts:
            #this code will skip links with [HTML] tag and throw error for links that are only "Get it at UWaterloo"
            try:
                if extract.find('span', attrs={'class':'gsc_title_ggt'}).text == "[PDF]":
                    return extract.find('a')['href']
                else:
                    print("html tag, will figure out later")
                    return None
            except:
                print ("get it at waterloo link, will figure out later")
                return None


class Citation:
    def __init__(self):
        self.k = None
        
        
        
        
class PaperReferenceProcessor:
    #assuming type is PDF
    def __init__ (self):
        self.references = []
            
    def getPdfContent (self, pdfUrl):
        
        content =""
        remoteFile = urlopen(Request(pdfUrl)).read()
        localFile = BytesIO(remoteFile)

        pdf = PyPDF2.PdfFileReader(localFile)
        
        for pageNum in range(pdf.getNumPages()):
            content+= pdf.getPage(pageNum).extractText()
            
        return self.standardize(content)
    
    def getReferencesContent(self, pdfUrl):
        
        pdfContent = self.getPdfContent(pdfUrl)
        index = pdfContent.find("references")
        if (index is None):
            print("can't find reference sections")
            return -1
        
        while (index!=-1):
            pdfContent = pdfContent[index +10:]
            index = pdfContent.find("references")
        
        
        
        return pdfContent
    
    def getCitesToAuthor (self, last_name, pdfContent):

        index = pdfContent.find("references")
        if (index==-1):
            print("can't find reference sections")
            return -1
        
        
        refContent = pdfContent[index:]
        
        counter = 0
        while (refContent.find(last_name)!=-1):
            refIndex = refContent.find(last_name)
            counter+=1
            refContent = refContent[refIndex+len(last_name):]
        
        return counter

    #removes line breaks, white space, and puts it to lower case
    def standardize(self, str):
        return str.replace("\n", "").replace(" ", "").lower()



#vas = AcademicPublisher('https://scholar.google.ca/citations?user=_yWPQWoAAAAJ&hl=en&oi=ao', 2)
#print(vas.getPaperCitationsByIndex(1))
#print (vas.getPapers())
#print (vas.getNumCitesByPaper(0, 0))


'''paper = Paper("https://scholar.google.ca/citations?view_op=view_citation&hl=en&user=ajvCoo4AAAAJ&citation_for_view=ajvCoo4AAAAJ:9yKSN-GCB0IC")
print (paper.findAllAuthors('Min Chen, Sergio Gonzalez, Anthonasias Vasilakos', "Body Area Networks: A Survey"))'''


'''extractor = GscPdfExtractor('https://scholar.google.ca/scholar?oi=bibs&hl=en&oe=ASCII&cites=2412871699215781213&as_sdt=5')
print(extractor.findPaperUrls())'''


p = PaperReferenceProcessor()
print(p.getReferencesContent("http://dro.dur.ac.uk/6128/1/6128.pdf"))
#print(p.getCitesToAuthor(vas, p.getPdfContent('http://www.diva-portal.org/smash/get/diva2:517321/FULLTEXT02')))


#g = GscPdfExtractor()
#print(g.findPdfUrlFromInfo('https://scholar.google.ca/citations?view_op=view_citation&hl=en&user=_yWPQWoAAAAJ&citation_for_view=_yWPQWoAAAAJ:_xSYboBqXhAC'))

#test_paper = Paper('https://scholar.google.ca/citations?view_op=view_citation&hl=en&user=_yWPQWoAAAAJ&citation_for_view=_yWPQWoAAAAJ:_xSYboBqXhAC')
#print(test_paper.getPdfUrl())
#print(test_paper.getcitedByUrl())
#print(test_paper.getInfo())


    
        
