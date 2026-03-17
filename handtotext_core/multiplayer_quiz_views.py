"""
Pair Quiz Views - Real-time collaborative quiz sessions
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from datetime import timedelta
from .models import PairQuizSession
from .services.gemini_service import GeminiService
from .decorators import check_feature_access_class_based
import logging
import random

logger = logging.getLogger(__name__)

# Pre-defined quiz questions pool for instant quiz generation
GENERAL_KNOWLEDGE_QUESTIONS = [
   {
        "id": 1,
        "question": "Which Indian state is known as the 'Land of the Rising Sun'?",
        "options": ["Assam", "Arunachal Pradesh", "Nagaland", "Manipur"],
        "correctAnswer": "Arunachal Pradesh",
        "correctAnswerIndex": 1
      },
      {
        "id": 2,
        "question": "The Chipko Movement originated in which Indian state?",
        "options": ["Himachal Pradesh", "Uttarakhand", "Madhya Pradesh", "Rajasthan"],
        "correctAnswer": "Uttarakhand",
        "correctAnswerIndex": 1
      },
      {
        "id": 3,
        "question": "Which Article of the Indian Constitution deals with the Right to Education?",
        "options": ["Article 19", "Article 21A", "Article 25", "Article 32"],
        "correctAnswer": "Article 21A",
        "correctAnswerIndex": 1
      },
      {
        "id": 4,
        "question": "The Konkan Railway connects which two cities?",
        "options": ["Mumbai to Goa", "Roha to Mangalore", "Pune to Kochi", "Mumbai to Kochi"],
        "correctAnswer": "Roha to Mangalore",
        "correctAnswerIndex": 1
      },
      {
        "id": 5,
        "question": "Which Indian city is known as the 'Manchester of South India'?",
        "options": ["Bangalore", "Coimbatore", "Chennai", "Hyderabad"],
        "correctAnswer": "Coimbatore",
        "correctAnswerIndex": 1
      },
      {
        "id": 6,
        "question": "The Loktak Lake is located in which state?",
        "options": ["Assam", "Manipur", "Meghalaya", "Tripura"],
        "correctAnswer": "Manipur",
        "correctAnswerIndex": 1
      },
      {
        "id": 7,
        "question": "Who was the first Indian to win an individual Olympic gold medal?",
        "options": ["PT Usha", "Abhinav Bindra", "Milkha Singh", "Sushil Kumar"],
        "correctAnswer": "Abhinav Bindra",
        "correctAnswerIndex": 1
      },
      {
        "id": 8,
        "question": "The Nalanda University was located in which present-day Indian state?",
        "options": ["Uttar Pradesh", "Bihar", "West Bengal", "Odisha"],
        "correctAnswer": "Bihar",
        "correctAnswerIndex": 1
      },
      {
        "id": 9,
        "question": "Which Indian state is the largest producer of coffee?",
        "options": ["Kerala", "Tamil Nadu", "Karnataka", "Andhra Pradesh"],
        "correctAnswer": "Karnataka",
        "correctAnswerIndex": 2
      },
      {
        "id": 10,
        "question": "The Hubballi-Dharwad cities are located in which state?",
        "options": ["Maharashtra", "Karnataka", "Telangana", "Andhra Pradesh"],
        "correctAnswer": "Karnataka",
        "correctAnswerIndex": 1
      },
      {
        "id": 11,
        "question": "Which mountain pass connects Leh to Kashmir?",
        "options": ["Rohtang Pass", "Zoji La", "Nathu La", "Khardung La"],
        "correctAnswer": "Zoji La",
        "correctAnswerIndex": 1
      },
      {
        "id": 12,
        "question": "The Indian Space Research Organisation (ISRO) headquarters is located in which city?",
        "options": ["Mumbai", "Chennai", "Bangalore", "Thiruvananthapuram"],
        "correctAnswer": "Bangalore",
        "correctAnswerIndex": 2
      },
      {
        "id": 13,
        "question": "Which Indian state celebrates the festival of Onam?",
        "options": ["Tamil Nadu", "Karnataka", "Kerala", "Andhra Pradesh"],
        "correctAnswer": "Kerala",
        "correctAnswerIndex": 2
      },
      {
        "id": 14,
        "question": "The Gir National Park is located in which state?",
        "options": ["Rajasthan", "Gujarat", "Madhya Pradesh", "Maharashtra"],
        "correctAnswer": "Gujarat",
        "correctAnswerIndex": 1
      },
      {
        "id": 15,
        "question": "Which Indian city is known as the 'Silicon Valley of India'?",
        "options": ["Hyderabad", "Pune", "Bangalore", "Chennai"],
        "correctAnswer": "Bangalore",
        "correctAnswerIndex": 2
      },
      {
        "id": 16,
        "question": "The Tungabhadra River flows through which Indian states?",
        "options": ["Karnataka and Andhra Pradesh", "Maharashtra and Karnataka", "Tamil Nadu and Kerala", "Telangana and Odisha"],
        "correctAnswer": "Karnataka and Andhra Pradesh",
        "correctAnswerIndex": 0
      },
      {
        "id": 17,
        "question": "Which Indian freedom fighter was known as 'Netaji'?",
        "options": ["Jawaharlal Nehru", "Subhas Chandra Bose", "Sardar Patel", "Bhagat Singh"],
        "correctAnswer": "Subhas Chandra Bose",
        "correctAnswerIndex": 1
      },
      {
        "id": 18,
        "question": "The Ajanta and Ellora Caves are located in which Indian state?",
        "options": ["Madhya Pradesh", "Maharashtra", "Karnataka", "Rajasthan"],
        "correctAnswer": "Maharashtra",
        "correctAnswerIndex": 1
      },
      {
        "id": 19,
        "question": "Which is the highest civilian award in India?",
        "options": ["Padma Vibhushan", "Bharat Ratna", "Padma Bhushan", "Padma Shri"],
        "correctAnswer": "Bharat Ratna",
        "correctAnswerIndex": 1
      },
      {
        "id": 20,
        "question": "The Sundarbans mangrove forest is shared between India and which other country?",
        "options": ["Nepal", "Bangladesh", "Myanmar", "Bhutan"],
        "correctAnswer": "Bangladesh",
        "correctAnswerIndex": 1
      },
      {
        "id": 21,
        "question": "Which Indian state is known as the 'Land of Five Rivers'?",
        "options": ["Haryana", "Punjab", "Himachal Pradesh", "Uttarakhand"],
        "correctAnswer": "Punjab",
        "correctAnswerIndex": 1
      },
      {
        "id": 22,
        "question": "The Kaziranga National Park is famous for which animal?",
        "options": ["Bengal Tiger", "Asiatic Lion", "One-horned Rhinoceros", "Indian Elephant"],
        "correctAnswer": "One-horned Rhinoceros",
        "correctAnswerIndex": 2
      },
      {
        "id": 23,
        "question": "Which Indian city is called the 'Pink City'?",
        "options": ["Udaipur", "Jaisalmer", "Jaipur", "Jodhpur"],
        "correctAnswer": "Jaipur",
        "correctAnswerIndex": 2
      },
      {
        "id": 24,
        "question": "The Battle of Plassey was fought in which year?",
        "options": ["1757", "1764", "1857", "1947"],
        "correctAnswer": "1757",
        "correctAnswerIndex": 0
      },
      {
        "id": 25,
        "question": "Which Indian state has the highest literacy rate?",
        "options": ["Tamil Nadu", "Maharashtra", "Kerala", "Goa"],
        "correctAnswer": "Kerala",
        "correctAnswerIndex": 2
      },
      {
        "id": 26,
        "question": "The Cellular Jail is located in which Indian territory?",
        "options": ["Lakshadweep", "Andaman and Nicobar Islands", "Daman and Diu", "Puducherry"],
        "correctAnswer": "Andaman and Nicobar Islands",
        "correctAnswerIndex": 1
      },
      {
        "id": 27,
        "question": "Which river is known as the 'Sorrow of Bihar'?",
        "options": ["Gandak", "Kosi", "Ganga", "Son"],
        "correctAnswer": "Kosi",
        "correctAnswerIndex": 1
      },
      {
        "id": 28,
        "question": "The Indian National Congress was founded in which year?",
        "options": ["1885", "1905", "1857", "1947"],
        "correctAnswer": "1885",
        "correctAnswerIndex": 0
      },
      {
        "id": 29,
        "question": "Which Indian state is the largest producer of tea?",
        "options": ["Kerala", "West Bengal", "Assam", "Tamil Nadu"],
        "correctAnswer": "Assam",
        "correctAnswerIndex": 2
      },
      {
        "id": 30,
        "question": "The Qutub Minar is located in which city?",
        "options": ["Agra", "Delhi", "Jaipur", "Lucknow"],
        "correctAnswer": "Delhi",
        "correctAnswerIndex": 1
      },
      {
        "id": 31,
        "question": "Which Indian state has the largest forest cover?",
        "options": ["Madhya Pradesh", "Arunachal Pradesh", "Chhattisgarh", "Odisha"],
        "correctAnswer": "Madhya Pradesh",
        "correctAnswerIndex": 0
      },
      {
        "id": 32,
        "question": "The Gateway of India was built to commemorate the visit of which British monarch?",
        "options": ["Queen Victoria", "King Edward VII", "King George V", "Queen Elizabeth II"],
        "correctAnswer": "King George V",
        "correctAnswerIndex": 2
      },
      {
        "id": 33,
        "question": "Which Indian state is known as the 'Spice Garden of India'?",
        "options": ["Tamil Nadu", "Karnataka", "Kerala", "Andhra Pradesh"],
        "correctAnswer": "Kerala",
        "correctAnswerIndex": 2
      },
      {
        "id": 34,
        "question": "The Chilika Lake is located in which Indian state?",
        "options": ["West Bengal", "Odisha", "Andhra Pradesh", "Tamil Nadu"],
        "correctAnswer": "Odisha",
        "correctAnswerIndex": 1
      },
      {
        "id": 35,
        "question": "Who was the first woman Prime Minister of India?",
        "options": ["Pratibha Patil", "Indira Gandhi", "Sarojini Naidu", "Sushma Swaraj"],
        "correctAnswer": "Indira Gandhi",
        "correctAnswerIndex": 1
      },
      {
        "id": 36,
        "question": "Which Indian state is the largest producer of wheat?",
        "options": ["Punjab", "Haryana", "Uttar Pradesh", "Madhya Pradesh"],
        "correctAnswer": "Uttar Pradesh",
        "correctAnswerIndex": 2
      },
      {
        "id": 37,
        "question": "The Howrah Bridge is located in which Indian city?",
        "options": ["Mumbai", "Kolkata", "Chennai", "Hyderabad"],
        "correctAnswer": "Kolkata",
        "correctAnswerIndex": 1
      },
      {
        "id": 38,
        "question": "Which Indian state celebrates Bihu festival?",
        "options": ["West Bengal", "Assam", "Odisha", "Manipur"],
        "correctAnswer": "Assam",
        "correctAnswerIndex": 1
      },
      {
        "id": 39,
        "question": "The Sardar Sarovar Dam is built on which river?",
        "options": ["Ganges", "Narmada", "Godavari", "Krishna"],
        "correctAnswer": "Narmada",
        "correctAnswerIndex": 1
      },
      {
        "id": 40,
        "question": "Which Indian city is known as the 'City of Pearls'?",
        "options": ["Chennai", "Visakhapatnam", "Hyderabad", "Bangalore"],
        "correctAnswer": "Hyderabad",
        "correctAnswerIndex": 2
      },
      {
        "id": 41,
        "question": "The Rann of Kutch is located in which Indian state?",
        "options": ["Rajasthan", "Gujarat", "Maharashtra", "Madhya Pradesh"],
        "correctAnswer": "Gujarat",
        "correctAnswerIndex": 1
      },
      {
        "id": 42,
        "question": "Who designed the Indian National Flag?",
        "options": ["Mahatma Gandhi", "Pingali Venkayya", "Jawaharlal Nehru", "Rabindranath Tagore"],
        "correctAnswer": "Pingali Venkayya",
        "correctAnswerIndex": 1
      },
      {
        "id": 43,
        "question": "Which Indian state is the largest producer of rubber?",
        "options": ["Tamil Nadu", "Karnataka", "Kerala", "Andhra Pradesh"],
        "correctAnswer": "Kerala",
        "correctAnswerIndex": 2
      },
      {
        "id": 44,
        "question": "The Victoria Memorial is located in which city?",
        "options": ["Mumbai", "Delhi", "Kolkata", "Chennai"],
        "correctAnswer": "Kolkata",
        "correctAnswerIndex": 2
      },
      {
        "id": 45,
        "question": "Which Indian state has the highest population?",
        "options": ["Maharashtra", "Bihar", "West Bengal", "Uttar Pradesh"],
        "correctAnswer": "Uttar Pradesh",
        "correctAnswerIndex": 3
      },
      {
        "id": 46,
        "question": "The Sabarmati Ashram is associated with which leader?",
        "options": ["Sardar Patel", "Mahatma Gandhi", "Jawaharlal Nehru", "Subhas Chandra Bose"],
        "correctAnswer": "Mahatma Gandhi",
        "correctAnswerIndex": 1
      },
      {
        "id": 47,
        "question": "Which Indian state is known as the 'Rice Bowl of India'?",
        "options": ["Punjab", "Haryana", "Andhra Pradesh", "West Bengal"],
        "correctAnswer": "Andhra Pradesh",
        "correctAnswerIndex": 2
      },
      {
        "id": 48,
        "question": "The Mysore Palace is located in which Indian state?",
        "options": ["Tamil Nadu", "Kerala", "Karnataka", "Andhra Pradesh"],
        "correctAnswer": "Karnataka",
        "correctAnswerIndex": 2
      },
      {
        "id": 49,
        "question": "Which Indian freedom fighter is known as the 'Iron Man of India'?",
        "options": ["Bhagat Singh", "Sardar Vallabhbhai Patel", "Lala Lajpat Rai", "Bal Gangadhar Tilak"],
        "correctAnswer": "Sardar Vallabhbhai Patel",
        "correctAnswerIndex": 1
      },
      {
        "id": 50,
        "question": "The Bhakra Nangal Dam is built on which river?",
        "options": ["Yamuna", "Sutlej", "Beas", "Ravi"],
        "correctAnswer": "Sutlej",
        "correctAnswerIndex": 1
      },
      {
        "id": 51,
        "question": "Which Indian city is called the 'Garden City of India'?",
        "options": ["Chandigarh", "Bangalore", "Pune", "Mysore"],
        "correctAnswer": "Bangalore",
        "correctAnswerIndex": 1
      },
      {
        "id": 52,
        "question": "The Brahmaputra River enters India through which state?",
        "options": ["Assam", "Arunachal Pradesh", "Meghalaya", "Manipur"],
        "correctAnswer": "Arunachal Pradesh",
        "correctAnswerIndex": 1
      },
      {
        "id": 53,
        "question": "Which Indian state is the largest producer of silk?",
        "options": ["West Bengal", "Karnataka", "Assam", "Tamil Nadu"],
        "correctAnswer": "Karnataka",
        "correctAnswerIndex": 1
      },
      {
        "id": 54,
        "question": "The Red Fort was built by which Mughal Emperor?",
        "options": ["Akbar", "Jahangir", "Shah Jahan", "Aurangzeb"],
        "correctAnswer": "Shah Jahan",
        "correctAnswerIndex": 2
      },
      {
        "id": 55,
        "question": "Which Indian state is known as the 'Land of Rising Sun'?",
        "options": ["Manipur", "Arunachal Pradesh", "Nagaland", "Mizoram"],
        "correctAnswer": "Arunachal Pradesh",
        "correctAnswerIndex": 1
      },
      {
        "id": 56,
        "question": "The Golden Temple is located in which city?",
        "options": ["Chandigarh", "Ludhiana", "Amritsar", "Jalandhar"],
        "correctAnswer": "Amritsar",
        "correctAnswerIndex": 2
      },
      {
        "id": 57,
        "question": "Which Indian state has the largest area?",
        "options": ["Madhya Pradesh", "Maharashtra", "Rajasthan", "Uttar Pradesh"],
        "correctAnswer": "Rajasthan",
        "correctAnswerIndex": 2
      },
      {
        "id": 58,
        "question": "The Jallianwala Bagh massacre took place in which year?",
        "options": ["1919", "1920", "1921", "1922"],
        "correctAnswer": "1919",
        "correctAnswerIndex": 0
      },
      {
        "id": 59,
        "question": "Which Indian city is known as the 'Diamond City'?",
        "options": ["Mumbai", "Ahmedabad", "Surat", "Rajkot"],
        "correctAnswer": "Surat",
        "correctAnswerIndex": 2
      },
      {
        "id": 60,
        "question": "The Periyar Wildlife Sanctuary is located in which state?",
        "options": ["Tamil Nadu", "Karnataka", "Kerala", "Andhra Pradesh"],
        "correctAnswer": "Kerala",
        "correctAnswerIndex": 2
      },
      {
        "id": 61,
        "question": "Who was the first President of India?",
        "options": ["Jawaharlal Nehru", "Dr. Rajendra Prasad", "S. Radhakrishnan", "Zakir Husain"],
        "correctAnswer": "Dr. Rajendra Prasad",
        "correctAnswerIndex": 1
      },
      {
        "id": 62,
        "question": "Which Indian state is the largest producer of sugarcane?",
        "options": ["Maharashtra", "Punjab", "Uttar Pradesh", "Tamil Nadu"],
        "correctAnswer": "Uttar Pradesh",
        "correctAnswerIndex": 2
      },
      {
        "id": 63,
        "question": "The Char Minar is located in which city?",
        "options": ["Delhi", "Agra", "Hyderabad", "Lucknow"],
        "correctAnswer": "Hyderabad",
        "correctAnswerIndex": 2
      },
      {
        "id": 64,
        "question": "Which Indian state celebrates Pongal festival?",
        "options": ["Kerala", "Karnataka", "Tamil Nadu", "Andhra Pradesh"],
        "correctAnswer": "Tamil Nadu",
        "correctAnswerIndex": 2
      },
      {
        "id": 65,
        "question": "The Hirakud Dam is built on which river?",
        "options": ["Godavari", "Krishna", "Mahanadi", "Narmada"],
        "correctAnswer": "Mahanadi",
        "correctAnswerIndex": 2
      },
      {
        "id": 66,
        "question": "Which Indian city is known as the 'City of Joy'?",
        "options": ["Mumbai", "Kolkata", "Delhi", "Chennai"],
        "correctAnswer": "Kolkata",
        "correctAnswerIndex": 1
      },
      {
        "id": 67,
        "question": "The Valley of Flowers National Park is located in which state?",
        "options": ["Himachal Pradesh", "Uttarakhand", "Jammu and Kashmir", "Sikkim"],
        "correctAnswer": "Uttarakhand",
        "correctAnswerIndex": 1
      },
      {
        "id": 68,
        "question": "Who wrote the Indian National Anthem 'Jana Gana Mana'?",
        "options": ["Bankim Chandra Chatterjee", "Rabindranath Tagore", "Sarojini Naidu", "Subramanya Bharathi"],
        "correctAnswer": "Rabindranath Tagore",
        "correctAnswerIndex": 1
      },
      {
        "id": 69,
        "question": "Which Indian state is the largest producer of cotton?",
        "options": ["Maharashtra", "Gujarat", "Punjab", "Haryana"],
        "correctAnswer": "Gujarat",
        "correctAnswerIndex": 1
      },
      {
        "id": 70,
        "question": "The Hawa Mahal is located in which city?",
        "options": ["Udaipur", "Jodhpur", "Jaipur", "Jaisalmer"],
        "correctAnswer": "Jaipur",
        "correctAnswerIndex": 2
      },
      {
        "id": 71,
        "question": "Which Indian state has the smallest population?",
        "options": ["Goa", "Sikkim", "Mizoram", "Arunachal Pradesh"],
        "correctAnswer": "Sikkim",
        "correctAnswerIndex": 1
      },
      {
        "id": 72,
        "question": "The Dandi March was led by which leader?",
        "options": ["Jawaharlal Nehru", "Mahatma Gandhi", "Sardar Patel", "Subhas Chandra Bose"],
        "correctAnswer": "Mahatma Gandhi",
        "correctAnswerIndex": 1
      },
      {
        "id": 73,
        "question": "Which Indian state is known as the 'Sugar Bowl of India'?",
        "options": ["Punjab", "Haryana", "Uttar Pradesh", "Maharashtra"],
        "correctAnswer": "Uttar Pradesh",
        "correctAnswerIndex": 2
      },
      {
        "id": 74,
        "question": "The India Gate was designed by which architect?",
        "options": ["Herbert Baker", "Edwin Lutyens", "Robert Tor Russell", "Henry Irwin"],
        "correctAnswer": "Edwin Lutyens",
        "correctAnswerIndex": 1
      },
      {
        "id": 75,
        "question": "Which Indian state celebrates Durga Puja with great fervor?",
        "options": ["Bihar", "Odisha", "West Bengal", "Assam"],
        "correctAnswer": "West Bengal",
        "correctAnswerIndex": 2
      },
      {
        "id": 76,
        "question": "The Tehri Dam is built on which river?",
        "options": ["Ganga", "Yamuna", "Bhagirathi", "Alaknanda"],
        "correctAnswer": "Bhagirathi",
        "correctAnswerIndex": 2
      },
      {
        "id": 77,
        "question": "Which Indian city is known as the 'Steel City of India'?",
        "options": ["Bhilai", "Durgapur", "Jamshedpur", "Bokaro"],
        "correctAnswer": "Jamshedpur",
        "correctAnswerIndex": 2
      },
      {
        "id": 78,
        "question": "The Nanda Devi National Park is located in which state?",
        "options": ["Himachal Pradesh", "Uttarakhand", "Sikkim", "Jammu and Kashmir"],
        "correctAnswer": "Uttarakhand",
        "correctAnswerIndex": 1
      },
      {
        "id": 79,
        "question": "Who was the first woman to climb Mount Everest from India?",
        "options": ["Bachendri Pal", "Santosh Yadav", "Arunima Sinha", "Premlata Agarwal"],
        "correctAnswer": "Bachendri Pal",
        "correctAnswerIndex": 0
      },
      {
        "id": 80,
        "question": "Which Indian state is the largest producer of mangoes?",
        "options": ["Maharashtra", "Andhra Pradesh", "Uttar Pradesh", "Gujarat"],
        "correctAnswer": "Uttar Pradesh",
        "correctAnswerIndex": 2
      },
      {
        "id": 81,
        "question": "The Amer Fort is located in which city?",
        "options": ["Udaipur", "Jaipur", "Jodhpur", "Bikaner"],
        "correctAnswer": "Jaipur",
        "correctAnswerIndex": 1
      },
      {
        "id": 82,
        "question": "Which Indian state has the highest per capita income?",
        "options": ["Maharashtra", "Goa", "Delhi", "Haryana"],
        "correctAnswer": "Goa",
        "correctAnswerIndex": 1
      },
      {
        "id": 83,
        "question": "The Quit India Movement was launched in which year?",
        "options": ["1940", "1942", "1944", "1945"],
        "correctAnswer": "1942",
        "correctAnswerIndex": 1
      },
      {
        "id": 84,
        "question": "Which Indian state is known as the 'Fruit Bowl of India'?",
        "options": ["Uttarakhand", "Himachal Pradesh", "Jammu and Kashmir", "Sikkim"],
        "correctAnswer": "Himachal Pradesh",
        "correctAnswerIndex": 1
      },
      {
        "id": 85,
        "question": "The Meenakshi Temple is located in which city?",
        "options": ["Chennai", "Madurai", "Thanjavur", "Kanchipuram"],
        "correctAnswer": "Madurai",
        "correctAnswerIndex": 1
      },
      {
        "id": 86,
        "question": "Which Indian state celebrates Hornbill Festival?",
        "options": ["Manipur", "Nagaland", "Mizoram", "Meghalaya"],
        "correctAnswer": "Nagaland",
        "correctAnswerIndex": 1
      },
      {
        "id": 87,
        "question": "The Nagarjuna Sagar Dam is built on which river?",
        "options": ["Godavari", "Krishna", "Kaveri", "Tungabhadra"],
        "correctAnswer": "Krishna",
        "correctAnswerIndex": 1
      },
      {
        "id": 88,
        "question": "Which Indian city is known as the 'City of Nawabs'?",
        "options": ["Delhi", "Hyderabad", "Lucknow", "Bhopal"],
        "correctAnswer": "Lucknow",
        "correctAnswerIndex": 2
      },
      {
        "id": 89,
        "question": "The Bandipur National Park is located in which state?",
        "options": ["Tamil Nadu", "Kerala", "Karnataka", "Andhra Pradesh"],
        "correctAnswer": "Karnataka",
        "correctAnswerIndex": 2
      },
      {
        "id": 90,
        "question": "Who was the first Indian woman to win an Olympic medal?",
        "options": ["PT Usha", "Karnam Malleswari", "Mary Kom", "Saina Nehwal"],
        "correctAnswer": "Karnam Malleswari",
        "correctAnswerIndex": 1
      },
      {
        "id": 91,
        "question": "Which Indian state is the largest producer of bananas?",
        "options": ["Kerala", "Maharashtra", "Tamil Nadu", "Gujarat"],
        "correctAnswer": "Tamil Nadu",
        "correctAnswerIndex": 2
      },
      {
        "id": 92,
        "question": "The Fatehpur Sikri was built by which Mughal Emperor?",
        "options": ["Babur", "Humayun", "Akbar", "Jahangir"],
        "correctAnswer": "Akbar",
        "correctAnswerIndex": 2
      },
      {
        "id": 93,
        "question": "Which Indian state has the smallest area?",
        "options": ["Goa", "Sikkim", "Tripura", "Manipur"],
        "correctAnswer": "Goa",
        "correctAnswerIndex": 0
      },
      {
        "id": 94,
        "question": "The Simon Commission came to India in which year?",
        "options": ["1927", "1928", "1929", "1930"],
        "correctAnswer": "1928",
        "correctAnswerIndex": 1
      },
      {
        "id": 95,
        "question": "Which Indian state is known as the 'Jewel of India'?",
        "options": ["Kerala", "Goa", "Manipur", "Sikkim"],
        "correctAnswer": "Manipur",
        "correctAnswerIndex": 2
      },
      {
        "id": 96,
        "question": "The Brihadeeswara Temple is located in which city?",
        "options": ["Chennai", "Madurai", "Thanjavur", "Trichy"],
        "correctAnswer": "Thanjavur",
        "correctAnswerIndex": 2
      },
      {
        "id": 97,
        "question": "Which Indian state celebrates Gangaur Festival?",
        "options": ["Gujarat", "Rajasthan", "Madhya Pradesh", "Haryana"],
        "correctAnswer": "Rajasthan",
        "correctAnswerIndex": 1
      },{
        "id": 98,
        "question": "Which Indian city is known as the 'Queen of the Arabian Sea'?",
        "options": ["Mumbai", "Goa", "Kochi", "Mangalore"],
        "correctAnswer": "Kochi",
        "correctAnswerIndex": 2
      },
      {
        "id": 99,
        "question": "The Keoladeo National Park is located in which state?",
        "options": ["Haryana", "Rajasthan", "Uttar Pradesh", "Madhya Pradesh"],
        "correctAnswer": "Rajasthan",
        "correctAnswerIndex": 1
      },
      {
        "id": 100,
        "question": "The Keoladeo National Park is located in which state?",
        "options": ["Haryana", "Rajasthan", "Uttar Pradesh", "Madhya Pradesh"],
        "correctAnswer": "Rajasthan",
        "correctAnswerIndex": 1
      },
]


def get_random_questions(num_questions=10, difficulty='medium'):
    """Get random questions from the question pool"""
    available_questions = GENERAL_KNOWLEDGE_QUESTIONS.copy()
    random.shuffle(available_questions)
    
    # Select the requested number of questions
    selected = available_questions[:min(num_questions, len(available_questions))]
    
    # Format for the quiz
    return {
        "success": True,
        "quiz": {
            "title": f"General Knowledge Challenge - {difficulty.capitalize()}",
            "topic": "General Knowledge",
            "difficulty": difficulty,
            "questions": selected
        }
    }


@method_decorator(csrf_exempt, name='dispatch')
class CreatePairQuizView(APIView):
    """Create a new pair quiz session"""
    
    def post(self, request):
        try:
            logger.info(f"[CreatePairQuiz] Request received: userId={request.data.get('userId')}")
            user_id = request.data.get('userId')
            quiz_config = request.data.get('quizConfig', {})
            
            if not user_id:
                return Response(
                    {'error': 'userId is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate questions instantly from pre-defined pool
            difficulty = quiz_config.get('difficulty', 'medium')
            num_questions = quiz_config.get('numQuestions', 10)
            
            quiz_data = get_random_questions(num_questions=num_questions, difficulty=difficulty)
            
            # Create session
            session = PairQuizSession.objects.create(
                host_user_id=user_id,
                quiz_config=quiz_config,
                questions=quiz_data['quiz']['questions'],
                expires_at=timezone.now() + timedelta(minutes=30)
            )
            session.session_code = session.generate_session_code()
            session.save()
            
            return Response({
                'sessionId': str(session.id),
                'sessionCode': session.session_code,
                'status': session.status,
                'hostUserId': session.host_user_id,
                'quizConfig': session.quiz_config,
                'questions': quiz_data['quiz']['questions'],
                'currentQuestionIndex': 0,
                'hostAnswers': {},
                'partnerAnswers': {},
                'expiresAt': session.expires_at.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            logger.error(f"Error creating pair quiz: {str(e)}")
            return Response(
                {'error': f'Failed to create pair quiz: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class JoinPairQuizView(APIView):
    """Join an existing pair quiz session"""
    
    def post(self, request):
        logger.info("=== JoinPairQuizView.post() called ===")
        try:
            logger.info(f"Join request received - Content-Type: {request.content_type}")
            logger.info(f"Join request data: {request.data}")
            
            user_id = request.data.get('userId')
            session_code = request.data.get('sessionCode')
            
            if not user_id or not session_code:
                logger.error(f"Missing required fields - userId: {user_id}, sessionCode: {session_code}")
                return Response(
                    {'error': 'userId and sessionCode are required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Find session
            try:
                session = PairQuizSession.objects.get(
                    session_code=session_code.upper()
                )
            except PairQuizSession.DoesNotExist:
                return Response(
                    {'error': 'Invalid session code'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Validate session
            if session.is_expired():
                session.status = 'cancelled'
                session.save()
                return Response(
                    {'error': 'Session has expired'},
                    status=status.HTTP_410_GONE
                )
            
            if session.status != 'waiting':
                return Response(
                    {'error': 'Session is not available for joining'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if session.partner_user_id:
                return Response(
                    {'error': 'Session is already full'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Join session
            session.partner_user_id = user_id
            session.status = 'active'
            session.started_at = timezone.now()
            session.save()
            
            return Response({
                'sessionId': str(session.id),
                'sessionCode': session.session_code,
                'status': session.status,
                'hostUserId': session.host_user_id,
                'partnerUserId': session.partner_user_id,
                'quizConfig': session.quiz_config,
                'questions': session.questions,
                'currentQuestionIndex': session.current_question_index,
                'hostAnswers': session.host_answers or {},
                'partnerAnswers': session.partner_answers or {}
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error joining pair quiz: {str(e)}")
            return Response(
                {'error': f'Failed to join pair quiz: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class PairQuizSessionView(APIView):
    """Get pair quiz session details"""
    
    def get(self, request, session_id):
        try:
            session = PairQuizSession.objects.get(id=session_id)
            
            return Response({
                'sessionId': str(session.id),
                'sessionCode': session.session_code,
                'status': session.status,
                'hostUserId': session.host_user_id,
                'partnerUserId': session.partner_user_id,
                'quizConfig': session.quiz_config,
                'questions': session.questions,
                'currentQuestionIndex': session.current_question_index,
                'hostAnswers': session.host_answers,
                'partnerAnswers': session.partner_answers,
                'timerSeconds': session.timer_seconds,
                'hostScore': session.host_score,
                'partnerScore': session.partner_score,
                'startedAt': session.started_at.isoformat() if session.started_at else None,
                'completedAt': session.completed_at.isoformat() if session.completed_at else None
            }, status=status.HTTP_200_OK)
            
        except PairQuizSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error fetching session: {str(e)}")
            return Response(
                {'error': f'Failed to fetch session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class CancelPairQuizView(APIView):
    """Cancel a pair quiz session"""
    
    def post(self, request, session_id):
        try:
            user_id = request.data.get('userId')
            reason = request.data.get('reason', 'User cancelled')
            
            session = PairQuizSession.objects.get(id=session_id)
            
            # Verify user is participant
            if user_id not in [session.host_user_id, session.partner_user_id]:
                return Response(
                    {'error': 'Unauthorized to cancel this session'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            session.status = 'cancelled'
            session.completed_at = timezone.now()
            session.save()
            
            return Response({
                'sessionId': str(session.id),
                'status': session.status,
                'reason': reason
            }, status=status.HTTP_200_OK)
            
        except PairQuizSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error cancelling session: {str(e)}")
            return Response(
                {'error': f'Failed to cancel session: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
