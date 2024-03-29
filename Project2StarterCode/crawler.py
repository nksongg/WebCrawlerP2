import logging
import re
from urllib.parse import urlparse, parse_qs , urlunparse
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
        self.recent_traps = []
        self.max_recent_traps = 20


        # #keep track of urls with fragments
        # self.fragment_url = set()
        
        
    def start_crawling(self):
        """
        This method starts the crawling process which is scraping urls from the next available link in frontier and adding
        the scraped links to the frontier
        """
        outlinks_count = 0
        
        while self.frontier.has_next_url():
            url = self.frontier.get_next_url()
            logger.info("Fetching URL %s ... Fetched: %s, Queue size: %s", url, self.frontier.fetched, len(self.frontier))
            url_data = self.corpus.fetch_url(url)

            self.download_urls.append(url)
            
            for next_link in self.extract_next_links(url_data):
                #pass in content, to keep track of page size
                if self.is_valid(next_link):
                    outlinks_count+=1
                    if self.corpus.get_file_name(next_link) is not None:
                        self.frontier.add_url(next_link)
                        
            #update most_outlinks
            if outlinks_count > self.most_outlinks["count"]:
                 self.most_outlinks = {'url': url_data['url'],"count":outlinks_count}
                 
            outlinks_count = 0
        
    #     self.write_to_file("fragment_links.txt",url + '\n')



    # def write_to_file(self,filename,text):
    #     with open(filename,'a', encoding ='utf-8') as file:
    #         file.write(text)
    #         for i in self.fragment_url:
    #             file.write(i + "\n")
            
    def add_to_recent_traps(self,url):
        self.recent_traps.append(url)
        if len(self.recent_traps) > self.max_recent_traps:
            self.recent_traps.pop(0)  


    def generate_analytics_report(self):
        report = {}
    
        report['subdomain_count'] = self.subdomain_count
        report['most_outlinks'] = self.most_outlinks
        report['downloaded_urls_count'] = len(self.download_urls)
        report['downloaded_urls'] = (self.download_urls)
        report['identified_traps_count'] = len(self.identified_traps)
        report['identified_traps'] = self.identified_traps
        report['longest_page'] = self.longest_page
    
        sorted_word_count = sorted(self.word_count.items(), key=lambda x: x[1], reverse=True)
        report['top_50_words'] = sorted_word_count[:50]

        return report
    
    def write_analytics_report_to_file(self, file_name="crawler_analytics_report.txt"):
        report = self.generate_analytics_report()
        with open(file_name, "w") as file:
            for key, value in report.items():
                file.write(f"{key}: {value}\n\n\n")
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
                content = url_data["content"]
                content_type = url_data.get("content_type",'')
                if isinstance(content, tuple):
                    content, content_type = content
                
                if isinstance(content,bytes):
                    encoding = 'utf-8'
                    if 'charset=' in content_type:
                        encoding = content_type.split('charset')[-1].split(';')[0].strip()
                        #decode binary content to a string
                    content = content.decode(encoding) 
                if isinstance(content,str):
                    pass
                
                
                # #decode binary content to a string
                # content = url_data["content"].decode(encoding)
                #parse HTML content
                htmlFile = html.fromstring(content)
                htmlFile.make_links_absolute(url_data["url"])
            
                #update word counts excluding html markup
                text = htmlFile.text_content()
                token_list = self.word_token_count(text)
                for token in token_list:
                    if token not in self.STOP_WORDS:
                        self.word_count[token] = self.word_count.get(token,0) + 1

                if len(token_list) > self.longest_page["count"]:
                    self.longest_page = {"url": url_data['url'],"count":len(token_list)}
                    
                    
                
                current_url_parse = urlparse(url_data["url"])
                for link in htmlFile.iterlinks():
                    #update redirect and final url information in dictionary
                    if (link[0].tag == 'meta' and 'refresh' in link[0].get('http-equiv', '').lower()):
                        url_data["final_url"] = link
                        redirect_url_dict = self.corpus.fetch_url(link)
                        redirect_url_dict["is_redirected"] = True

                    absolute_url = link[2]
                    outgoing_url_parse = urlparse(absolute_url)
                    # if link contains fragment and has the same base url leading upto the fragment, add to trap list
                    if ((outgoing_url_parse.fragment) and (urlunparse(outgoing_url_parse._replace(fragment='')) == urlunparse(current_url_parse._replace(fragment='')))):
                            self.identified_traps.append(link[2])
                            self.add_to_recent_traps(link[2])
                    # else add to output link
                    else:
                        outputLinks.append(absolute_url)
                


                #updates subdomain count
                subdomain = current_url_parse.hostname
                self.subdomain_count[subdomain] = self.subdomain_count.get(subdomain,0) + 1   

                
            except Exception as e:
                logger.error(f"error parsing content from {url_data['url']}: {e}")\
                
                #TEMPORARY
                #write errors to a file
                with open('errorList.txt','a', encoding ='utf-8') as file:
                    file.write(str(e)+" current url: "+ url_data["url"] +"\n")

                

        
        return outputLinks


    def is_valid(self, url,content=None):
        """
        Function returns True or False based on whether the url has to be fetched or not. This is a great place to
        filter out crawler traps. Duplicated urls will be taken care of by frontier. You don't need to check for duplication
        in this method
        """
        max_length = 200
        max_query_parameters = 5
        similarity_threshold = 4
        parsed = urlparse(url)
        
        for trap_url in self.recent_traps:
            differences = sum(c1 != c2 for c1, c2 in zip(url,trap_url)) + abs(len(url) - len(trap_url))
            if differences <= similarity_threshold:
                self.identified_traps.append(url)
                self.add_to_recent_traps(url)
                return False
        
        #keeps track of length of URL if it gets too long don't fetch
        if len(url) > max_length:
            self.identified_traps.append(url)
            self.add_to_recent_traps(url)
            return False
    
        
        # non-consecutive repeating patterns
        path_segments = [segment for segment in parsed.path.split('/') if segment]
        if len(path_segments) != len(set(path_segments)):
            self.identified_traps.append(url)
            self.add_to_recent_traps(url)
            return False
        
        query_params = parse_qs(parsed.query)
        param_terms = {"week" , "day" , "date"}
        for param, values in query_params.items():
            if len(values) != len(set(values)):
                return False
            if any(param_terms in param.lower() for param_terms in param_terms):
                self.identified_traps.append(url)
                self.add_to_recent_traps(url)
                return False
            
        
        #check for dynamic links  by checking for # of &(parameters) in the query
        if len(query_params) > max_query_parameters:
            self.identified_traps.append(url)
            self.add_to_recent_traps(url)
            return False
        
        ########################################### functions we tried and adjusted 
        # #check if the URL contains a fragment (#)
        # if parsed.fragment:
        #     #adds the url without the fragment to the set
        #     self.fragment_url.add(urlunparse(parsed._replace(fragment=''))+'#')
        #     #if the url before the fragment exists in the set, don't visit
        #     if urlunparse(parsed._replace(fragment=''))+'#' in self.fragment_url:
        #         self.identified_traps.append(url)
        #         return False
        
        #check for repeated patterns, r = raw string, (/.+?/) -> capture group, checks for regex with '/' at the beginning and end, and .+? matches 
        # one or more of any character, \1+ compares the last regex with the current regex
        # if re.search(r'(/.+?/)\1+', url):
        #     self.identified_traps.append(url)
        #     return False
        
        if parsed.scheme not in set(["http", "https"]):
            return False
        
        # self.write_to_file("crawler_links.txt",url + '\n')
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
        
