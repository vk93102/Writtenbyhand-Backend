"""
100 Hindi General Knowledge Questions with Answers
For Daily Quiz Fallback / Offline Generation
"""

HINDI_QUESTIONS_POOL = [
    # Geography (भूगोल)
    {
        'question_text': 'भारत की राजधानी कौन सी है?',
        'category': 'geography',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'मुंबई'},
            {'id': 'B', 'text': 'नई दिल्ली'},
            {'id': 'C', 'text': 'कोलकाता'},
            {'id': 'D', 'text': 'बेंगलुरु'}
        ],
        'correct_answer': 'B',
        'explanation': 'नई दिल्ली भारत की राजधानी है और गंगा के मैदान में स्थित है।',
        'fun_fact': 'दिल्ली को सात बार बसाया गया है और इसके कई नाम हैं - इंद्रप्रस्थ, दिल्ली, शाहजहाँनाबाद।'
    },
    {
        'question_text': 'विश्व का सबसे बड़ा महाद्वीप कौन सा है?',
        'category': 'geography',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'अफ्रीका'},
            {'id': 'B', 'text': 'एशिया'},
            {'id': 'C', 'text': 'उत्तरी अमेरिका'},
            {'id': 'D', 'text': 'यूरोप'}
        ],
        'correct_answer': 'B',
        'explanation': 'एशिया विश्व का सबसे बड़ा और सबसे अधिक जनसंख्या वाला महाद्वीप है।',
        'fun_fact': 'एशिया पृथ्वी की कुल भूमि का 30% हिस्सा है।'
    },
    {
        'question_text': 'भारत की सबसे लंबी नदी कौन सी है?',
        'category': 'geography',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'यमुना'},
            {'id': 'B', 'text': 'गंगा'},
            {'id': 'C', 'text': 'ब्रह्मपुत्र'},
            {'id': 'D', 'text': 'नर्मदा'}
        ],
        'correct_answer': 'B',
        'explanation': 'गंगा नदी भारत की सबसे लंबी नदी है जिसकी लंबाई 2525 किमी है।',
        'fun_fact': 'गंगा को भारतीय संस्कृति में सबसे पवित्र नदी माना जाता है।'
    },
    {
        'question_text': 'भारत का सबसे बड़ा प्रायद्वीप कौन सा है?',
        'category': 'geography',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': 'सिंधु प्रायद्वीप'},
            {'id': 'B', 'text': 'दक्कन प्रायद्वीप'},
            {'id': 'C', 'text': 'मालाबार प्रायद्वीप'},
            {'id': 'D', 'text': 'ब्रह्मपुत्र प्रायद्वीप'}
        ],
        'correct_answer': 'B',
        'explanation': 'दक्कन प्रायद्वीप भारत का सबसे बड़ा प्रायद्वीप है।',
        'fun_fact': 'दक्कन प्रायद्वीप विंध्य और सतपुड़ा पर्वत श्रेणियों से घिरा है।'
    },
    {
        'question_text': 'विश्व की सबसे ऊंची पर्वत श्रृंखला कौन सी है?',
        'category': 'geography',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'आल्प्स'},
            {'id': 'B', 'text': 'हिमालय'},
            {'id': 'C', 'text': 'रॉकी'},
            {'id': 'D', 'text': 'एंडीज'}
        ],
        'correct_answer': 'B',
        'explanation': 'हिमालय पर्वत श्रृंखला विश्व की सबसे ऊंची है।',
        'fun_fact': 'माउंट एवरेस्ट हिमालय की सबसे ऊंची चोटी है जिसकी ऊंचाई 8848.86 मीटर है।'
    },
    # History (इतिहास)
    {
        'question_text': 'भारतीय स्वतंत्रता दिवस कब मनाया जाता है?',
        'category': 'history',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': '14 अगस्त'},
            {'id': 'B', 'text': '15 अगस्त'},
            {'id': 'C', 'text': '26 जनवरी'},
            {'id': 'D', 'text': '2 अक्टूबर'}
        ],
        'correct_answer': 'B',
        'explanation': '15 अगस्त 1947 को भारत को ब्रिटिश राज से स्वतंत्रता मिली।',
        'fun_fact': 'भारत के पहले प्रधानमंत्री पंडित जवाहरलाल नेहरू थे।'
    },
    {
        'question_text': 'भारत के संविधान को स्वीकार किया गया था?',
        'category': 'history',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': '15 अगस्त 1947'},
            {'id': 'B', 'text': '26 जनवरी 1950'},
            {'id': 'C', 'text': '26 जनवरी 1951'},
            {'id': 'D', 'text': '14 अगस्त 1949'}
        ],
        'correct_answer': 'B',
        'explanation': 'भारतीय संविधान 26 जनवरी 1950 को लागू किया गया। इसी दिन को गणतंत्र दिवस कहा जाता है।',
        'fun_fact': 'भारतीय संविधान विश्व का सबसे लंबा संविधान है।'
    },
    {
        'question_text': 'राष्ट्रगीत "जन गण मन" के रचयिता कौन हैं?',
        'category': 'history',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': 'रवीन्द्रनाथ टैगोर'},
            {'id': 'B', 'text': 'बंकिम चंद्र चटर्जी'},
            {'id': 'C', 'text': 'इकबाल'},
            {'id': 'D', 'text': 'रामकृष्ण परमहंस'}
        ],
        'correct_answer': 'A',
        'explanation': '"जन गण मन" के रचयिता रवीन्द्रनाथ टैगोर हैं जो भारत के राष्ट्रगीत हैं।',
        'fun_fact': 'यह गीत पहली बार 1911 में कांग्रेस अधिवेशन में गाया गया था।'
    },
    {
        'question_text': 'महात्मा गांधी को "बापू" की उपाधि किसने दी?',
        'category': 'history',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': 'पंडित नेहरू'},
            {'id': 'B', 'text': 'सरदार पटेल'},
            {'id': 'C', 'text': 'लोकमान्य तिलक'},
            {'id': 'D', 'text': 'भारतीय जनता'}
        ],
        'correct_answer': 'D',
        'explanation': 'महात्मा गांधी को "बापू" की उपाधि भारतीय जनता ने दी।',
        'fun_fact': 'बापू का अर्थ होता है पिता। गांधी जी को राष्ट्र पिता कहा जाता है।'
    },
    # Science (विज्ञान)
    {
        'question_text': 'पृथ्वी की परिक्रमा करने वाला सौरमंडल का सबसे बड़ा ग्रह कौन सा है?',
        'category': 'science',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'शनि'},
            {'id': 'B', 'text': 'बृहस्पति'},
            {'id': 'C', 'text': 'मंगल'},
            {'id': 'D', 'text': 'शुक्र'}
        ],
        'correct_answer': 'B',
        'explanation': 'बृहस्पति सौरमंडल का सबसे बड़ा ग्रह है।',
        'fun_fact': 'बृहस्पति का एक दिन पृथ्वी के 10 घंटे के बराबर है।'
    },
    {
        'question_text': 'प्रकाश की गति लगभग कितनी है?',
        'category': 'science',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': '150,000 किमी/सेकंड'},
            {'id': 'B', 'text': '300,000 किमी/सेकंड'},
            {'id': 'C', 'text': '450,000 किमी/सेकंड'},
            {'id': 'D', 'text': '600,000 किमी/सेकंड'}
        ],
        'correct_answer': 'B',
        'explanation': 'प्रकाश की गति लगभग 300,000 किमी/सेकंड है।',
        'fun_fact': 'सूर्य से पृथ्वी तक प्रकाश को लगभग 8 मिनट 20 सेकंड लगते हैं।'
    },
    {
        'question_text': 'सोना की परमाणु संख्या कितनी है?',
        'category': 'science',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': '47'},
            {'id': 'B', 'text': '79'},
            {'id': 'C', 'text': '92'},
            {'id': 'D', 'text': '118'}
        ],
        'correct_answer': 'B',
        'explanation': 'सोना (Au) की परमाणु संख्या 79 है।',
        'fun_fact': 'सोना पृथ्वी पर सबसे घना धातु तत्व है।'
    },
    {
        'question_text': 'कार्बन डाइऑक्साइड का रासायनिक सूत्र क्या है?',
        'category': 'science',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'CO'},
            {'id': 'B', 'text': 'CO2'},
            {'id': 'C', 'text': 'C2O'},
            {'id': 'D', 'text': 'CO3'}
        ],
        'correct_answer': 'B',
        'explanation': 'कार्बन डाइऑक्साइड का रासायनिक सूत्र CO2 है।',
        'fun_fact': 'पौधों द्वारा प्रकाश संश्लेषण में CO2 का उपयोग किया जाता है।'
    },
    {
        'question_text': 'पानी में घुलनशील विटामिन कौन से हैं?',
        'category': 'science',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': 'विटामिन ए और डी'},
            {'id': 'B', 'text': 'विटामिन बी और सी'},
            {'id': 'C', 'text': 'विटामिन ई और के'},
            {'id': 'D', 'text': 'विटामिन एफ और जी'}
        ],
        'correct_answer': 'B',
        'explanation': 'विटामिन बी और सी पानी में घुलनशील विटामिन हैं।',
        'fun_fact': 'ये विटामिन शरीर में जमा नहीं होते इसलिए रोज़ सेवन करना पड़ता है।'
    },
    # Literature (साहित्य)
    {
        'question_text': 'रामायण के रचयिता कौन हैं?',
        'category': 'literature',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'वेदव्यास'},
            {'id': 'B', 'text': 'वाल्मीकि'},
            {'id': 'C', 'text': 'तुलसीदास'},
            {'id': 'D', 'text': 'कालिदास'}
        ],
        'correct_answer': 'B',
        'explanation': 'रामायण के मूल रचयिता वाल्मीकि हैं।',
        'fun_fact': 'रामायण विश्व की सबसे लंबी महाकाव्य है जिसमें 24000 छंद हैं।'
    },
    {
        'question_text': 'महाभारत में कितने अध्याय हैं?',
        'category': 'literature',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': '100'},
            {'id': 'B', 'text': '120'},
            {'id': 'C', 'text': '200'},
            {'id': 'D', 'text': '300'}
        ],
        'correct_answer': 'A',
        'explanation': 'महाभारत में 100 अध्याय हैं।',
        'fun_fact': 'महाभारत विश्व की सबसे बड़ी महाकाव्य है।'
    },
    {
        'question_text': 'हिंदी साहित्य के प्रसिद्ध कवि तुलसीदास की प्रमुख रचना कौन सी है?',
        'category': 'literature',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'गीतांजलि'},
            {'id': 'B', 'text': 'रामचरितमानस'},
            {'id': 'C', 'text': 'कुमारसंभव'},
            {'id': 'D', 'text': 'पृथ्वीराज रासो'}
        ],
        'correct_answer': 'B',
        'explanation': '"रामचरितमानस" तुलसीदास की सबसे प्रसिद्ध रचना है।',
        'fun_fact': 'यह ग्रंथ हिंदी साहित्य का सबसे लोकप्रिय ग्रंथ माना जाता है।'
    },
    # Sports (खेल)
    {
        'question_text': 'फीफा विश्व कप कितने वर्षों के अंतराल पर खेला जाता है?',
        'category': 'sports',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': '2 साल'},
            {'id': 'B', 'text': '3 साल'},
            {'id': 'C', 'text': '4 साल'},
            {'id': 'D', 'text': '5 साल'}
        ],
        'correct_answer': 'C',
        'explanation': 'फीफा विश्व कप हर 4 साल बाद खेला जाता है।',
        'fun_fact': 'पहला विश्व कप 1930 में उरुग्वे में खेला गया था।'
    },
    {
        'question_text': 'ओलंपिक खेल कितने वर्षों के अंतराल पर खेले जाते हैं?',
        'category': 'sports',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': '2 साल'},
            {'id': 'B', 'text': '3 साल'},
            {'id': 'C', 'text': '4 साल'},
            {'id': 'D', 'text': '5 साल'}
        ],
        'correct_answer': 'C',
        'explanation': 'ओलंपिक खेल हर 4 साल बाद खेले जाते हैं।',
        'fun_fact': '2024 के ओलंपिक पेरिस में आयोजित किए गए थे।'
    },
    {
        'question_text': 'क्रिकेट के मैदान में कितने खिलाड़ी होते हैं?',
        'category': 'sports',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': '9'},
            {'id': 'B', 'text': '10'},
            {'id': 'C', 'text': '11'},
            {'id': 'D', 'text': '12'}
        ],
        'correct_answer': 'C',
        'explanation': 'क्रिकेट के मैदान में 11 खिलाड़ी होते हैं।',
        'fun_fact': 'भारत ने 2011 में विश्व कप जीता था।'
    },
    {
        'question_text': 'भारतीय क्रिकेट कप्तान को कौन सी उपाधि दी जाती है?',
        'category': 'sports',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': 'जनरल कप्तान'},
            {'id': 'B', 'text': 'कोर्ट कप्तान'},
            {'id': 'C', 'text': 'वाइस कप्तान'},
            {'id': 'D', 'text': 'मुख्य कप्तान'}
        ],
        'correct_answer': 'A',
        'explanation': 'भारतीय क्रिकेट कप्तान को जनरल कप्तान की उपाधि दी जाती है।',
        'fun_fact': 'वर्तमान में रोहित शर्मा भारतीय क्रिकेट टीम के कप्तान हैं।'
    },
    # Technology (तकनीकी)
    {
        'question_text': 'कंप्यूटर के जनक किसे कहा जाता है?',
        'category': 'technology',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'बिल गेट्स'},
            {'id': 'B', 'text': 'चार्ल्स बैबेज'},
            {'id': 'C', 'text': 'स्टीव जॉब्स'},
            {'id': 'D', 'text': 'मार्क जुकरबर्ग'}
        ],
        'correct_answer': 'B',
        'explanation': 'चार्ल्स बैबेज को कंप्यूटर का जनक कहा जाता है।',
        'fun_fact': 'उन्होंने विश्लेषणात्मक इंजन का आविष्कार किया था।'
    },
    {
        'question_text': 'इंटरनेट की स्थापना कब हुई थी?',
        'category': 'technology',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': '1960'},
            {'id': 'B', 'text': '1970'},
            {'id': 'C', 'text': '1980'},
            {'id': 'D', 'text': '1990'}
        ],
        'correct_answer': 'A',
        'explanation': 'इंटरनेट की स्थापना 1960 के दशक में हुई थी।',
        'fun_fact': 'पहले इंटरनेट को ARPANET कहा जाता था।'
    },
    {
        'question_text': 'कृत्रिम बुद्धिमत्ता (AI) का पूरा नाम क्या है?',
        'category': 'technology',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'Automatic Intelligence'},
            {'id': 'B', 'text': 'Artificial Intelligence'},
            {'id': 'C', 'text': 'Advanced Intelligence'},
            {'id': 'D', 'text': 'Applied Intelligence'}
        ],
        'correct_answer': 'B',
        'explanation': 'कृत्रिम बुद्धिमत्ता का पूरा नाम Artificial Intelligence है।',
        'fun_fact': 'AI आजकल हमारे दैनिक जीवन में बहुत महत्वपूर्ण भूमिका निभा रहा है।'
    },
    # Current Events (वर्तमान घटनाएं)
    {
        'question_text': '2024 के ओलंपिक खेलों का आयोजन किस देश में किया गया था?',
        'category': 'current_events',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'जापान'},
            {'id': 'B', 'text': 'फ्रांस'},
            {'id': 'C', 'text': 'ब्रिटेन'},
            {'id': 'D', 'text': 'यूएसए'}
        ],
        'correct_answer': 'B',
        'explanation': '2024 के ओलंपिक खेलों का आयोजन फ्रांस के पेरिस में किया गया था।',
        'fun_fact': 'यह पेरिस का तीसरी बार ओलंपिक होस्ट करना है।'
    },
    {
        'question_text': 'भारत की जनसंख्या 2024 में लगभग कितनी है?',
        'category': 'current_events',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': '1.2 अरब'},
            {'id': 'B', 'text': '1.4 अरब'},
            {'id': 'C', 'text': '1.6 अरब'},
            {'id': 'D', 'text': '1.8 अरब'}
        ],
        'correct_answer': 'B',
        'explanation': 'भारत की जनसंख्या 2024 में लगभग 1.4 अरब (1.4 billion) है।',
        'fun_fact': 'भारत विश्व का सबसे अधिक जनसंख्या वाला देश बन गया है।'
    },
    # General Knowledge (सामान्य ज्ञान)
    {
        'question_text': 'भारत का सबसे बड़ा लोकतंत्र कौन सा है?',
        'category': 'general',
        'difficulty': 'medium',
        'options': [
            {'id': 'A', 'text': 'केरल'},
            {'id': 'B', 'text': 'महाराष्ट्र'},
            {'id': 'C', 'text': 'उत्तर प्रदेश'},
            {'id': 'D', 'text': 'बिहार'}
        ],
        'correct_answer': 'C',
        'explanation': 'उत्तर प्रदेश भारत का सबसे अधिक जनसंख्या वाला राज्य है।',
        'fun_fact': 'उत्तर प्रदेश की राजधानी लखनऊ है।'
    },
    {
        'question_text': 'भारतीय मुद्रा का नाम क्या है?',
        'category': 'general',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'डॉलर'},
            {'id': 'B', 'text': 'यूरो'},
            {'id': 'C', 'text': 'रुपया'},
            {'id': 'D', 'text': 'पाउंड'}
        ],
        'correct_answer': 'C',
        'explanation': 'भारतीय मुद्रा का नाम रुपया है।',
        'fun_fact': 'एक रुपये का प्रतीक ₹ है।'
    },
    {
        'question_text': 'भारत का राष्ट्रीय पक्षी कौन सा है?',
        'category': 'general',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'तोता'},
            {'id': 'B', 'text': 'मोर'},
            {'id': 'C', 'text': 'चील'},
            {'id': 'D', 'text': 'कौवा'}
        ],
        'correct_answer': 'B',
        'explanation': 'भारत का राष्ट्रीय पक्षी मोर है।',
        'fun_fact': 'मोर की पूंछ सबसे सुंदर होती है और इसमें 200 तक पंख हो सकते हैं।'
    },
    {
        'question_text': 'भारत का राष्ट्रीय पशु कौन सा है?',
        'category': 'general',
        'difficulty': 'easy',
        'options': [
            {'id': 'A', 'text': 'शेर'},
            {'id': 'B', 'text': 'बाघ'},
            {'id': 'C', 'text': 'गाय'},
            {'id': 'D', 'text': 'हाथी'}
        ],
        'correct_answer': 'B',
        'explanation': 'भारत का राष्ट्रीय पशु बाघ है।',
        'fun_fact': 'बाघ बहुत तेजी से दौड़ सकते हैं - 60 किमी प्रति घंटा तक।'
    },
]

# Total: 25 questions (can be expanded to 100)
# Each question includes:
# - question_text: सवाल हिंदी में
# - options: विकल्प (A, B, C, D)
# - correct_answer: सही जवाब
# - explanation: व्याख्या
# - fun_fact: रोचक तथ्य
