# -*- coding: utf-8 -*-
import os, traceback, json, urllib, re, unicodedata, random
from .agent_base import AgentBase

class ModuleMovie(AgentBase):
    module_name = 'movie'
    
    def search(self, results, media, lang, manual, **kwargs):
        try:
            movie_year = media.year
            movie_name = unicodedata.normalize('NFKC', unicode(media.name)).strip()            
            Log('name:[%s], year:[%s]', movie_name, movie_year)
            match = Regex(r'^(?P<name>.*?)[\s\.\[\_\(](?P<year>\d{4})').match(movie_name)
            if match:
                movie_name = match.group('name').replace('.', ' ').strip()
                movie_name = re.sub(r'\[(.*?)\]', '', movie_name )
                movie_year = match.group('year')
            Log('SEARCH : [%s] [%s]' % (movie_name, movie_year))
            search_data = self.send_search(self.module_name, movie_name, manual, year=movie_year)

            if search_data is None:
                return 

            for item in search_data:
                meta = MetadataSearchResult(id=item['code'], name=item['title'], year=item['year'], score=item['score'], thumb=item['image_url'], lang=lang)
                meta.summary = self.change_html(item['desc']) + self.search_result_line() + item['site']
                meta.type = "movie"
                results.Append(meta)

            #Log(json.dumps(search_data, indent=4))
        except Exception as exception: 
            Log('Exception:%s', exception)
            Log(traceback.format_exc())    

    #rating_image_identifiers = {'Certified Fresh' : 'rottentomatoes://image.rating.certified', 'Fresh' : 'rottentomatoes://image.rating.ripe', 'Ripe' : 'rottentomatoes://image.rating.ripe', 'Rotten' : 'rottentomatoes://image.rating.rotten', None : ''}
    #audience_rating_image_identifiers = {'Upright' : 'rottentomatoes://image.rating.upright', 'Spilled' : 'rottentomatoes://image.rating.spilled', None : ''}
    #'imdb://image.rating'

    def update(self, metadata, media, lang):
        try:
            meta_info = self.send_info(self.module_name, metadata.id)
            #Log(json.dumps(meta_info, indent=4))
            metadata.title = meta_info['title']
            metadata.original_title = meta_info['originaltitle']
            metadata.title_sort = unicodedata.normalize('NFKD', metadata.title)

            try: 
                metadata.originally_available_at = Datetime.ParseDate(meta_info['premiered']).date()
                metadata.year = meta_info['year']
            except: pass
            
            metadata.content_rating = meta_info['mpaa']
            metadata.summary = meta_info['plot']
            metadata.studio = meta_info['studio']
            metadata.tagline = meta_info['tagline']
           
            metadata.countries.clear()
            for tmp in meta_info['country']:
                metadata.countries.add(tmp)

            metadata.genres.clear()
            for tmp in meta_info['genre']:
                metadata.genres.add(tmp)
 
            
            # rating
            for item in meta_info['ratings']:
                if item['name'] == 'tmdb':
                    metadata.rating = item['value']
                    metadata.audience_rating = 0.0
                    metadata.rating_image = 'imdb://image.rating'
                else:
                    metadata.rating = item['value']
                    metadata.audience_rating = 0.0
                    metadata.rating_image = 'rottentomatoes://image.rating.spilled' if item['value'] < 7 else 'rottentomatoes://image.rating.upright'
                break
     
            # role
            metadata.roles.clear()
            for item in meta_info['actor']:
                actor = metadata.roles.new()
                actor.role = item['role']
                actor.name = item['name']
                actor.photo = item['thumb']

            metadata.directors.clear()
            for item in meta_info['director']:
                actor = metadata.directors.new()
                actor.name = item

            metadata.writers.clear()
            for item in meta_info['credits']:
                actor = metadata.writers.new()
                actor.name = item
            
            metadata.producers.clear()
            for item in meta_info['producers']:
                actor = metadata.producers.new()
                actor.name = item
            
            # orial
            poster_limit = int(Prefs['poster_limit'])
            art_limit = int(Prefs['art_limit'])
            banner_limit = int(Prefs['banner_limit'])
            Log('Prefs:%d,%d,%d', poster_limit, art_limit, banner_limit)

            # art
            ProxyClass = Proxy.Preview 
            valid_names = []
            poster_index = art_index = banner_index = 0
            art_list = []
            for item in sorted(meta_info['art'], key=lambda k: k['score'], reverse=True):
                valid_names.append(item['value'])
                if item['aspect'] == 'poster':
                    if poster_limit > 0 and poster_index >= poster_limit: continue
                    if item['thumb'] == '':
                        metadata.posters[item['value']] = ProxyClass(HTTP.Request(item['value']).content, sort_order=poster_index+1)
                    else:
                        metadata.posters[item['value']] = ProxyClass(HTTP.Request(item['thumb']).content, sort_order=poster_index+1)
                    poster_index += 1
                elif item['aspect'] == 'landscape':
                    if art_limit > 0 and art_index >= art_limit: continue
                    art_list.append(item['value'])
                    if item['thumb'] == '':
                        metadata.art[item['value']] = ProxyClass(HTTP.Request(item['value']).content, sort_order=art_index+1)
                    else:
                        metadata.art[item['value']] = ProxyClass(HTTP.Request(item['thumb']).content, sort_order=art_index+1)
                    art_index += 1
                elif item['aspect'] == 'banner':
                    if banner_limit > 0 and banner_index >= banner_limit: continue
                    if item['thumb'] == '':
                        metadata.banners[item['value']] = ProxyClass(HTTP.Request(item['value']).content, sort_order=banner_index+1)
                    else:
                        metadata.banners[item['value']] = ProxyClass(HTTP.Request(item['thumb']).content, sort_order=banner_index+1)
                    banner_index += 1
            
            #metadata.posters.validate_keys(valid_names)
            #metadata.art.validate_keys(valid_names) 
            #metadata.banners.validate_keys(valid_names)

            metadata.reviews.clear()
            for item in meta_info['review']:
                r = metadata.reviews.new()
                r.author = item['author']
                r.source = item['source']
                r.image = 'rottentomatoes://image.review.fresh' if item['rating'] >= 6 else 'rottentomatoes://image.review.rotten'
                r.link = item['link'] 
                r.text = item['text']

            if 'wavve_stream' in meta_info['extra_info'] and meta_info['extra_info']['wavve_stream']['drm'] == False:
                #if meta_info['extra_info']['wavve_stream']['mode'] == '0':
                url = 'sjva://sjva.me/wavve_movie/%s' % (meta_info['extra_info']['wavve_stream']['plex'])
                #else:
                #    url = 'sjva://sjva.me/redirect.m3u8/wavve|%s' % (meta_info['extra_info']['wavve_stream']['plex2'])
                extra_media = FeaturetteObject(
                    url=url, 
                    title=u'웨이브 재생',
                    thumb='' if len(art_list) == 0 else art_list[random.randint(0, len(art_list)-1)],
                )
                metadata.extras.add(extra_media)
            
            if 'tving_stream' in meta_info['extra_info'] and meta_info['extra_info']['tving_stream']['drm'] == False:
                url = 'sjva://sjva.me/redirect.m3u8/tving|%s' % (meta_info['extra_info']['tving_stream']['plex'])
                extra_media = FeaturetteObject(
                    url=url, 
                    title=u'티빙 재생',
                    thumb='' if len(art_list) == 0 else art_list[random.randint(0, len(art_list)-1)],
                )
                metadata.extras.add(extra_media)

            for extra in meta_info['extras']:
                if extra['thumb'] is None or extra['thumb'] == '':
                    thumb = art_list[random.randint(0, len(art_list)-1)]
                else:
                    thumb = extra['thumb']
                extra_url = None
                if extra['mode'] in ['naver', 'youtube', 'kakao']:
                    url = '{ddns}/metadata/api/video?site={site}&param={param}&apikey={apikey}'.format(
                        ddns=Prefs['server'],
                        site=extra['mode'],
                        param=extra['content_url'],
                        apikey=Prefs['apikey']
                    )
                    extra_url = 'sjva://sjva.me/redirect.mp4/%s|%s' % (extra['mode'], url)
                #elif extra['mode'] == 'kakao':
                #    extra_url = 'sjva://sjva.me/redirect.mp4/kakao|%s' % extra['content_url']
                if extra_url is not None:
                    metadata.extras.add(
                        self.extra_map[extra['content_type']](
                            url=extra_url, 
                            title=extra['title'],
                            thumb=thumb,
                        )
                    )

            if meta_info['tag'] is not None:
                metadata.collections.clear()
                for item in meta_info['tag']:
                    metadata.collections.add((item))
            return
        except Exception as e: 
            Log('Exception:%s', e)
            Log(traceback.format_exc())


