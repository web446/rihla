"""Real photos for the seed data, from Wikimedia Commons (generated, then checked by eye).

Every photo is a real photograph shared under a free licence (Creative Commons or public
domain). Those licences require crediting the author, so each entry keeps the credit
("Author · licence") and the link to the photo's page. Shown on /credits.
"""

PHOTOS = {
    'country:turkey': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/3/31/Hot_air_balloons_over_valleys_near_G%C3%B6reme%2C_Cappadocia_at_dawn.JPG/1280px-Hot_air_balloons_over_valleys_near_G%C3%B6reme%2C_Cappadocia_at_dawn.JPG',
        'credit': 'MusikAnimal · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Hot_air_balloons_over_valleys_near_G%C3%B6reme,_Cappadocia_at_dawn.JPG',
    },
    'country:armenia': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6e/Monasterio_Khor_Virap%2C_Armenia%2C_2016-10-01%2C_DD_25.jpg/1280px-Monasterio_Khor_Virap%2C_Armenia%2C_2016-10-01%2C_DD_25.jpg',
        'credit': 'Diego Delso · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Monasterio_Khor_Virap,_Armenia,_2016-10-01,_DD_25.jpg',
    },
    'country:egypt': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/a/af/All_Gizah_Pyramids.jpg/1280px-All_Gizah_Pyramids.jpg',
        'credit': 'Ricardo Liberato · CC BY-SA 2.0',
        'source': 'https://commons.wikimedia.org/wiki/File:All_Gizah_Pyramids.jpg',
    },
    'country:jordan': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/4/40/Al-Khazneh_%28The_Treasury%29_2%2C_Petra%2C_Jordan.jpg/1280px-Al-Khazneh_%28The_Treasury%29_2%2C_Petra%2C_Jordan.jpg',
        'credit': 'Vyacheslav Argenberg · CC BY 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Al-Khazneh_(The_Treasury)_2,_Petra,_Jordan.jpg',
    },
    'country:georgia': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/4/4f/Kazbek%2C_Gergeti_Trinity_Church_2017.jpg/1280px-Kazbek%2C_Gergeti_Trinity_Church_2017.jpg',
        'credit': 'MaxBenidze · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Kazbek,_Gergeti_Trinity_Church_2017.jpg',
    },
    'country:malaysia': {
        'url': 'https://upload.wikimedia.org/wikipedia/commons/2/2a/The_Datai_Beach_Langkawi_-_panoramio.jpg',
        'credit': 'alhafis · CC BY 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:The_Datai_Beach_Langkawi_-_panoramio.jpg',
    },
    'monument:Hagia Sophia': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/2/22/Hagia_Sophia_Mars_2013.jpg/960px-Hagia_Sophia_Mars_2013.jpg',
        'credit': 'Arild Vågen · CC BY-SA 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Hagia_Sophia_Mars_2013.jpg',
    },
    'monument:Topkapi Palace': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/d/d5/Grand_Kiosk_of_Topkap%C4%B1_Palace_in_Istanbul%2C_Turkey_002.jpg/960px-Grand_Kiosk_of_Topkap%C4%B1_Palace_in_Istanbul%2C_Turkey_002.jpg',
        'credit': 'Moonik · CC BY-SA 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Grand_Kiosk_of_Topkap%C4%B1_Palace_in_Istanbul,_Turkey_002.jpg',
    },
    'monument:Basilica Cistern': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/c/cc/Basilica_Cistern_Istanbul_%28243857265%29.jpeg/960px-Basilica_Cistern_Istanbul_%28243857265%29.jpeg',
        'credit': 'Bhasker Thodla · CC BY 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Basilica_Cistern_Istanbul_(243857265).jpeg',
    },
    'monument:Ephesus': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/8/84/Ephesus_Celsus_Library_Fa%C3%A7ade.jpg/960px-Ephesus_Celsus_Library_Fa%C3%A7ade.jpg',
        'credit': 'Benh LIEU SONG · CC BY-SA 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Ephesus_Celsus_Library_Fa%C3%A7ade.jpg',
    },
    'monument:Goreme Open-Air Museum': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/6/60/G%C3%B6reme_Open_Air_Museum_01.jpg/960px-G%C3%B6reme_Open_Air_Museum_01.jpg',
        'credit': 'Bernard Gagnon · CC BY-SA 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:G%C3%B6reme_Open_Air_Museum_01.jpg',
    },
    'monument:Garni Temple': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b9/Templo_de_Garni%2C_Armenia%2C_2016-10-02%2C_DD_03.jpg/960px-Templo_de_Garni%2C_Armenia%2C_2016-10-02%2C_DD_03.jpg',
        'credit': 'Diego Delso · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Templo_de_Garni,_Armenia,_2016-10-02,_DD_03.jpg',
    },
    'monument:Geghard Monastery': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/7/7b/Monasterio_de_Geghard%2C_Armenia%2C_2016-10-02%2C_DD_63.jpg/960px-Monasterio_de_Geghard%2C_Armenia%2C_2016-10-02%2C_DD_63.jpg',
        'credit': 'Diego Delso · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Monasterio_de_Geghard,_Armenia,_2016-10-02,_DD_63.jpg',
    },
    'monument:Wings of Tatev': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/5/54/The_Wings_Of_Tatev_%2837778475201%29.jpg/960px-The_Wings_Of_Tatev_%2837778475201%29.jpg',
        'credit': 'Clay Gilliland · CC BY-SA 2.0',
        'source': 'https://commons.wikimedia.org/wiki/File:The_Wings_Of_Tatev_(37778475201).jpg',
    },
    'monument:Cascade Complex': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/1/17/Yerevan%2C_Cascade_of_Yerevan%2C_Armenia.jpg/960px-Yerevan%2C_Cascade_of_Yerevan%2C_Armenia.jpg',
        'credit': 'Vyacheslav Argenberg · CC BY 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Yerevan,_Cascade_of_Yerevan,_Armenia.jpg',
    },
    'monument:Khor Virap': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/7/7a/Khor_Virap_Monastery_2%2C_Ararat_Plain%2C_Armenia.jpg/960px-Khor_Virap_Monastery_2%2C_Ararat_Plain%2C_Armenia.jpg',
        'credit': 'Vyacheslav Argenberg · CC BY 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Khor_Virap_Monastery_2,_Ararat_Plain,_Armenia.jpg',
    },
    'monument:Pyramids of Giza & the Sphinx': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/d/db/Great_Sphinx_of_Giza_%28%D8%A3%D8%A8%D9%88_%D8%A7%D9%84%D9%87%D9%88%D9%84%29.jpg/960px-Great_Sphinx_of_Giza_%28%D8%A3%D8%A8%D9%88_%D8%A7%D9%84%D9%87%D9%88%D9%84%29.jpg',
        'credit': 'Petar Milošević · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Great_Sphinx_of_Giza_(%D8%A3%D8%A8%D9%88_%D8%A7%D9%84%D9%87%D9%88%D9%84).jpg',
    },
    'monument:Grand Egyptian Museum': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/0/04/Grand_Egyptian_Museum_2025.jpg/960px-Grand_Egyptian_Museum_2025.jpg',
        'credit': 'Amr F.Nagy · Public domain',
        'source': 'https://commons.wikimedia.org/wiki/File:Grand_Egyptian_Museum_2025.jpg',
    },
    'monument:Karnak Temple': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c9/Templo_de_Karnak%2C_Luxor%2C_Egipto%2C_2022-04-03%2C_DD_142.jpg/960px-Templo_de_Karnak%2C_Luxor%2C_Egipto%2C_2022-04-03%2C_DD_142.jpg',
        'credit': 'Diego Delso · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Templo_de_Karnak,_Luxor,_Egipto,_2022-04-03,_DD_142.jpg',
    },
    'monument:Ras Mohammed National Park': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/0/0a/Pez_%C3%A1ngel_real_%28Pygoplites_diacanthus%29%2C_parque_nacional_Ras_Muhammad%2C_Egipto%2C_2022-03-26%2C_DD_155.jpg/960px-Pez_%C3%A1ngel_real_%28Pygoplites_diacanthus%29%2C_parque_nacional_Ras_Muhammad%2C_Egipto%2C_2022-03-26%2C_DD_155.jpg',
        'credit': 'Diego Delso · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Pez_%C3%A1ngel_real_(Pygoplites_diacanthus),_parque_nacional_Ras_Muhammad,_Egipto,_2022-03-26,_DD_155.jpg',
    },
    'monument:Valley of the Kings': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/9/92/Luxor_Valley_of_the_Kings_R01.jpg/960px-Luxor_Valley_of_the_Kings_R01.jpg',
        'credit': 'Marc Ryckaert · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Luxor_Valley_of_the_Kings_R01.jpg',
    },
    'monument:Petra': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/6/6a/Ad_Deir_%28The_Monastery%29%2C_El_Deir%2C_Top%2C_Petra%2C_Jordan.jpg/960px-Ad_Deir_%28The_Monastery%29%2C_El_Deir%2C_Top%2C_Petra%2C_Jordan.jpg',
        'credit': 'Vyacheslav Argenberg · CC BY 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Ad_Deir_(The_Monastery),_El_Deir,_Top,_Petra,_Jordan.jpg',
    },
    'monument:Wadi Rum Protected Area': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c2/Wadi_rum_desert.jpg/960px-Wadi_rum_desert.jpg',
        'credit': 'Peter Chisholm · CC0',
        'source': 'https://commons.wikimedia.org/wiki/File:Wadi_rum_desert.jpg',
    },
    'monument:Jerash': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/2/21/Jerash_Oval_Plaza_003.JPG/960px-Jerash_Oval_Plaza_003.JPG',
        'credit': 'لا روسا · CC BY-SA 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Jerash_Oval_Plaza_003.JPG',
    },
    'monument:Amman Citadel': {
        'url': 'https://upload.wikimedia.org/wikipedia/commons/1/1c/Temple_of_Hercules_-_Amman_citadel.jpg',
        'credit': 'AliAbuRas · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Temple_of_Hercules_-_Amman_citadel.jpg',
    },
    'monument:Dead Sea (Amman Beach)': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/7/70/Dead_Sea%2C_Jordan_02.jpg/960px-Dead_Sea%2C_Jordan_02.jpg',
        'credit': 'Bernard Gagnon · CC BY-SA 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Dead_Sea,_Jordan_02.jpg',
    },
    'monument:Narikala Fortress': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/9/9e/Wall_of_Narikala_Fortress%2C_Tbilisi.jpg/960px-Wall_of_Narikala_Fortress%2C_Tbilisi.jpg',
        'credit': 'Reda Kerbush · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Wall_of_Narikala_Fortress,_Tbilisi.jpg',
    },
    'monument:Gergeti Trinity Church': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/8/8a/Gergeti_Trinity_Church_and_Mt._Kazbeg_01.jpg/960px-Gergeti_Trinity_Church_and_Mt._Kazbeg_01.jpg',
        'credit': 'Braveheart · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Gergeti_Trinity_Church_and_Mt._Kazbeg_01.jpg',
    },
    'monument:Jvari Monastery': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/4/47/Georgia_Jvari_monastery_IMG_9345_2070.jpg/960px-Georgia_Jvari_monastery_IMG_9345_2070.jpg',
        'credit': 'Alexxx1979 · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Georgia_Jvari_monastery_IMG_9345_2070.jpg',
    },
    'monument:Uplistsikhe Cave Town': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/9/95/Uplistsikhe_view.jpg/960px-Uplistsikhe_view.jpg',
        'credit': 'EvgenyGenkin · CC BY-SA 3.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Uplistsikhe_view.jpg',
    },
    'monument:Sighnaghi Town Walls': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f3/Sighnaghi_town_wall_%28Georgia%29.jpg/960px-Sighnaghi_town_wall_%28Georgia%29.jpg',
        'credit': 'Sergey Sebelev · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Sighnaghi_town_wall_(Georgia).jpg',
    },
    'monument:Petronas Twin Towers Skybridge': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/c/c8/The_Twins_SE_Asia_2019_%2849171985716%29.jpg/960px-The_Twins_SE_Asia_2019_%2849171985716%29.jpg',
        'credit': 'James Kerwin · CC BY 2.0',
        'source': 'https://commons.wikimedia.org/wiki/File:The_Twins_SE_Asia_2019_(49171985716).jpg',
    },
    'monument:Batu Caves': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/0/09/Batu_Caves_View_from_Stairs_2015.jpg/960px-Batu_Caves_View_from_Stairs_2015.jpg',
        'credit': 'KQuhen · CC BY-SA 4.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Batu_Caves_View_from_Stairs_2015.jpg',
    },
    'monument:Langkawi SkyCab': {
        'url': 'https://upload.wikimedia.org/wikipedia/commons/f/f9/Langkawi_cablecar_bridge.jpg',
        'credit': 'Cheon Fong Liew · CC BY-SA 2.0',
        'source': 'https://commons.wikimedia.org/wiki/File:Langkawi_cablecar_bridge.jpg',
    },
    'monument:Penang Hill Funicular': {
        'url': 'https://thumb.wikimedia.org/wikipedia/commons/thumb/4/44/Penang_Hill_in_2023_04.jpg/960px-Penang_Hill_in_2023_04.jpg',
        'credit': 'Renek78 · CC0',
        'source': 'https://commons.wikimedia.org/wiki/File:Penang_Hill_in_2023_04.jpg',
    },
}
