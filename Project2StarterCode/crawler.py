import logging
import re
from urllib.parse import urlparse, parse_qs
from lxml import etree, html
from collections import defaultdict

logger = logging.getLogger(__name__)

class Crawler:
    """
    This class is responsible for scraping urls from the next available link in frontier and adding the scraped links to
    the frontier
    """
    STOP_WORDS = {"a","above","after","again","against","all","am","an","and","any","are","aren't","as","at","be","because","been","before","being","below","between","both","but","by","can't","cannot","could","couldn't","did","didn't","do","does","doesn't","doing","don't","down","during","each","few","for","from","further","had","hadn't","has","hasn't","have","haven't","having","he","he'd","he'll","he's","her","here","here's","hers","herself","him","himself","his","how","how's","i","i'd","i'll","i'm","i've","if","in","into","is","isn't","it","it's","its","itself","let's","me","more","most","mustn't","my","myself","no","nor","not","of","off","on","once","only","or","other","ought","our","ours","ourselves","out","over","own","same","shan't","she","she'd","she'll","she's","should","shouldn't","so","some","such","than","that","that's","the","their","theirs","them","themselves","then","there","there's","these","they","they'd","they'll","they're","they've","this","those","through","to","too","under","until","up","very","was","wasn't","we","we'd","we'll","we're","we've","were","weren't","what","what's","when","when's","where","where's","which","while","who","who's","whom","why","why's","with","won't","would","wouldn't","you","you'd","you'll","you're","you've","your","yours","yourself","yourselves"}

    def __init__(self, frontier, corpus):
        self.frontier = frontier
        self.corpus = corpus
        
        #keep track of subdomains it has visited and how many URLs it has processed from each of them
        self.subdomain_count = {}
        ##of links that ARE valid on a particular webpage
        self.most_outlinks = {"url":None, "count": 0}
        #List of the downloaded_urls
        self.download_urls = []
        #List of traps we have identified
        self.identified_traps = []
        #longest page in terms of words (not counting HTML markup)
        self.longest_page = {"url":None, "count": 0}
        #keeps track of word count (no stop words) in order for us to rank the top 50 most common words in the whole set
        self.word_count = {}
        
    def start_crawling(self):
        """
        This method starts the crawling process which is scraping urls from the next available link in frontier and adding
        the scraped links to the frontier
        """
        while self.frontier.has_next_url():
            url = self.frontier.get_next_url()
            logger.info("Fetching URL %s ... Fetched: %s, Queue size: %s", url, self.frontier.fetched, len(self.frontier))
            url_data = self.corpus.fetch_url(url)

            for next_link in self.extract_next_links(url_data):
                if self.is_valid(next_link):
                    if self.corpus.get_file_name(next_link) is not None:
                        self.frontier.add_url(next_link)



    def generate_analytics_report(self):
        report = {}
    
        report['subdomain_count'] = self.subdomain_count
        report['most_outlinks'] = self.most_outlinks
        report['downloaded_urls_count'] = len(self.download_urls)
        report['identified_traps'] = self.identified_traps
        report['longest_page'] = self.longest_page
    
        sorted_word_count = sorted(self.word_count.items(), key=lambda x: x[1], reverse=True)
        report['top_50_words'] = sorted_word_count[:50]

        return report
    
    def write_analytics_report_to_file(self, file_name="crawler_analytics_report.txt"):
        report = self.generate_analytics_report()
        with open(file_name, "w") as file:
            for key, value in report.items():
                file.write(f"{key}: {value}\n")
            file.write("\n")

    def word_token_count(self, text):
        tokenList = []
        new = True

        for char in text:     
            if not char: 
                break
            if char.isalnum() is False or char.isascii() is False: 
                try:
                    tokenList[-1] = tokenList[-1].lower()
                except:
                    pass   
                new = True
            elif new:
                tokenList.append(char)
                new = False
            else:
                tokenList[-1] = tokenList[-1]+char
        return tokenList
        
            
    def extract_next_links(self, url_data):
        """
        The url_data coming from the fetch_url method will be given as a parameter to this method. url_data contains the
        fetched url, the url content in binary format, and the size of the content in bytes. This method should return a
        list of urls in their absolute form (some links in the content are relative and needs to be converted to the
        absolute form). Validation of links is done later via is_valid method. It is not required to remove duplicates
        that have already been fetched. The frontier takes care of that.

        Suggested library: lxml
        """
        #tracks highest outlinks count
        outlinks_count = 0
        
        # list to hold the absolute URL's
        outputLinks = []  

        if url_data["content"] and url_data["http_code"] != 404:
            try:
                #decode binary content to a string
                content = url_data["content"].decode('utf-8')
                
                #parse HTML content
                htmlFile = html.fromstring(content)
                htmlFile.make_links_absolute(url_data["url"])
                
                #update word counts excluding html markup
                text = htmlFile.text_content()
                token_list = self.word_token_count(text)
                for token in token_list:
                    if token not in self.STOP_WORDS:
                        self.word_count[token] = self.word_count.get(token,0) + 1


                #text = etree.tostring(htmlFile,method='text',encoding='utf-8').decode('utf-8')
                # words = text.split()
                # for word in words:
                #     self.word_count[word] = self.word_count.get(word,0) + 1
                    
                    
                #extract URLS , temporary could probably implement the incrementing in is_valid
                urls = list(htmlFile.iterlinks())
                for link in urls:
                    absolute_url = link[2]
                    outputLinks.append(absolute_url)
                    outlinks_count+=1
                else:
                #also could implement the identified traps in is_valid
                    self.identified_traps.append(absolute_url)
               
                #update most_outlinks
                if outlinks_count > self.most_outlinks["count"]:
                     self.most_outlinks = {'url': url_data['url'],"count":outlinks_count}
                  
                #updates subdomain count
                parsed_url = urlparse(url_data['url'])
                subdomain = parsed_url.hostname
                self.subdomain_count[subdomain] = self.subdomain_count.get(subdomain,0) + 1   

                
            except Exception as e:
                logger.error(f"error parsing content from {url_data['url']}: {e}")
                
        #check to see if the content and http code has has a successful response
        # if url_data["content"] and url_data["http_code"] == 200:
        #     try:
        #         # decode the binary content using UTF-8 encoding
        #         content = url_data["content"].decode("utf-8")
        #         # attempts to capture within content, all of the anchor tags in the HTML content in both single and double quotes
        #         # ["\'] -> opening single or double quote, (.*?) -> capturing group that matches any character sequence except a 
        #         # newline and will be zero or more occurrences , ["\"] -> closing single or double quote
        #         urls = re.findall(r'href=["\'](.*?)["\']', content)
        #         #loop through each link we obtained from the webpage
        #         for href in urls:
        #             #parse the base url into components
        #             # scheme, netloc, path, params, query, fragment
        #             parsed_base = urlparse(url_data["url"])
                    
        #             #scheme - relative URL (prefixed with the scheme of the base URL)
        #             if href.startswith('//'):
        #                 absolute_url =  parsed_base.scheme + ':' + href
                        
        #             #root - relative URL (combined with the scheme and netloc of the base URL)
        #             elif href.startswith('/'):
        #                 absolute_url = parsed_base.scheme + '://' + parsed_base.netloc + href
                        
        #             #path - relative URL (path is constructed from the base URL and appended to the href)
        #             elif not href.startswith(('http://', 'https://')):
        #                 #break into path components and split the first element of the split
        #                 path = parsed_base.path.rsplit('/', 1)[0] + '/'
        #                 absolute_url = parsed_base.scheme + '://' + parsed_base.netloc + path + href
                        
        #             #already an absolute URL
        #             else:
        #                 absolute_url = href
                        
        #             #append the absolute_url to outputLinks    
        #             outputLinks.append(absolute_url)  
                      
        #     except Exception as e:
        #         logging.error(f"error extracting links: {e}")
        
        return outputLinks


    def is_valid(self, url):
        """
        Function returns True or False based on whether the url has to be fetched or not. This is a great place to
        filter out crawler traps. Duplicated urls will be taken care of by frontier. You don't need to check for duplication
        in this method
        """
        max_length = 150
        
        #keeps track of length of URL if it gets too long don't fetch
        if len(url) > max_length:
            return False
        
        parsed = urlparse(url)
        
        if parsed.scheme not in set(["http", "https"]):
            return False
        try:
            return ".ics.uci.edu" in parsed.hostname \
                   and not re.match(".*\.(css|js|bmp|gif|jpe?g|ico" + "|png|tiff?|mid|mp2|mp3|mp4" \
                                    + "|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf" \
                                    + "|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso|epub|dll|cnf|tgz|sha1" \
                                    + "|thmx|mso|arff|rtf|jar|csv" \
                                    + "|rm|smil|wmv|swf|wma|zip|rar|gz|pdf)$", parsed.path.lower())

        except TypeError:
            print("TypeError for ", parsed)
            return False
