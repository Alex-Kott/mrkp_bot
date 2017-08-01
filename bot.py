# -*- coding: utf-8 -*-
import telebot
from telebot import types
import cfg
from peewee import *
import re
import math
import json

bot = telebot.TeleBot(cfg.token)

#chid = -1001124459892 # test channel id
chid = -1001088809213 # https://t.me/feeltm
#like = "👍"
thumb_up = "👍"
like = "🌀" 
dislike = "👎"
poll = "poll" # пост-опрос
common = "common" # тип поста. обыкновенный пост с лайком и дизлайком под сообщением.
nolike = "nolike" # просто сообщение без лайка
empty = "▫️"

emoji = {like : 1, dislike : -1}
admins = {72639889, 5844335, 328241232}

db = SqliteDatabase('bot.db')

def xlikes(mp, p): 
	try:
		x = p / (mp / 100)
	except ZeroDivisionError:
		x = 0
	d = 14.3 # 100 / 7 (лайков)
	if p == 0:
		return empty
	else:
		n = math.ceil(x/d)
		return thumb_up * n

def decline(n):
	l = n - 10 * math.floor(n / 10)
	if l == 0:
		return "пока никто не проголосовал."
	if l in {1}:
		return "{} человек уже проголосовал.".format(l)
	elif l in {2, 3, 4}:
		return "{} человека уже проголосовало.".format(l)
	else:
		return "{} человек уже проголосовало.".format(l)		

class BaseModel(Model):

	class Meta:
		database = db

class Post(BaseModel):
	msg_id = IntegerField(unique = True, primary_key= True)
	likes = IntegerField(default = 0)
	dislikes = IntegerField(default = 0)

	def create_or_get(msg_id):
		try:
			with db.atomic():
				return Post.create(msg_id = msg_id)
		except:
			return Post.select().where(Post.msg_id == msg_id).get()

class Like(BaseModel):
	msg_id = IntegerField()
	like = IntegerField(default = 0) # 1 for like, -1 for dislike, 0 for mark absence
	user_id = IntegerField()

	def create_or_get(msg_id, user_id):
		try:
			with db.atomic():
				return Like.create(msg_id = msg_id, user_id = user_id)
		except:
			return Like.select().where((Like.msg_id == msg_id) & (Like.user_id == user_id)).get()

	class Meta:
		primary_key = CompositeKey('msg_id', 'user_id')

class Poll(BaseModel):
	msg_id = IntegerField()
	item = TextField()
	point = IntegerField(default = 0)

	def create_or_get(msg_id, item):
		try:
			with db.atomic():
				return Poll.create(msg_id = msg_id, item = item)
		except:
			return Poll.select().where((Poll.msg_id == msg_id) & (Poll.item == item)).get()

	def upd(msg_id):
		#for item in Scoreboard.get(Scoreboard.msg_id == msg_id):
		lst = (Scoreboard.select(Scoreboard, fn.Count(Scoreboard.user_id).alias('count'))
					    .where(Scoreboard.msg_id == msg_id)
					    .group_by(Scoreboard.item))

		polls = Poll.select().where(Poll.msg_id == msg_id)
		for p in polls:
			count = (Scoreboard.select(fn.Count(Scoreboard.user_id))
							   .where(Scoreboard.msg_id == msg_id & Scoreboard.item == p.item))
			#poll = Poll.get(Poll.msg_id == msg_id & Poll.item)
			p.point = count
			p.save()
			#print("{} {} {}".format(p.msg_id, p.item, p.point))

		for i in lst:
			#print("{} {} {} {}".format(i.msg_id, i.item, i.user_id, i.count))
			poll = Poll.get(Poll.msg_id == i.msg_id, Poll.item == i.item)
			poll.point = i.count
			poll.save()

	class Meta(BaseModel):
		primary_key = CompositeKey('msg_id', 'item')

class Scoreboard(BaseModel):
	msg_id = IntegerField()
	item = TextField()
	user_id = IntegerField()

	def vote(msg_id, item, user_id):
		#print("{} {} {}".format(msg_id, item, user_id))

		try:
			score = Scoreboard.get(Scoreboard.msg_id == msg_id, Scoreboard.user_id == user_id)
			if score.item == item:
				score.delete_instance()
			else:
				score.item = item
			score.save()
		except Exception as e:
			
			Scoreboard.create(msg_id = msg_id, item = item, user_id = user_id)
			#print("Create", end="\n\n")
			
			

		Poll.upd(msg_id)


class Message(BaseModel): # тип сообщения (опрос, обычный пост или что-то ещё). нужен при обработке колбэков
	msg_id = IntegerField(primary_key = True)
	user_id = IntegerField()
	msg_type = TextField()
	text = TextField()



@bot.message_handler(commands = ['init'])
def init(message):
	Like.create_table(fail_silently = True)
	Post.create_table(fail_silently = True)
	Poll.create_table(fail_silently = True)
	Message.create_table(fail_silently = True) 
	Scoreboard.create_table(fail_silently = True)
	


@bot.message_handler(content_types=['text'])
def new_post(message):
	#print(message)
	sid = message.chat.id
	if sid not in admins:
		return False
	keyboard = types.InlineKeyboardMarkup()

	if len(re.findall(r'\/nolike', message.text)) > 0: # проверка не является ли сообщение сообщением типа nolike
		msg_type = nolike
	elif len(re.findall(r'\/poll', message.text)) > 0: # не является ли сообщение опросом
		msg_type = poll
	else:
		msg_type = common

	if msg_type == poll:
		try:
			(text, items) = re.split(r'\/poll', message.text)
		except:
			bot(sid, "Вы ввели некорректные варианты опроса")
		item = re.split(r'\n', items.strip())
		msg_text = text
		for i in item:
			btn = types.InlineKeyboardButton(text = i, callback_data = i)
			keyboard.add(btn)
			msg_text += "\n{}\n{}0%\n".format(i, empty)
		msg_text += "\n👥 пока никто не проголосовал"

		sent = bot.send_message(chid, msg_text, parse_mode = "Markdown", reply_markup = keyboard)
		Message.create(msg_id = sent.message_id, user_id = sid, msg_type = poll, text = text)
		message = Message.select().where(Message.user_id == sid).order_by(Message.msg_id.desc()).get()
		item = list(set(item))
		for j in item:
			Poll.create(msg_id = message.msg_id, item = j, point = 0)
	if msg_type == common:
		like_btn = types.InlineKeyboardButton(text = like, callback_data = like)
		dislike_btn = types.InlineKeyboardButton(text = dislike, callback_data = dislike)
		#keyboard.add(like_btn, dislike_btn)
		keyboard.add(like_btn)
		sent = bot.send_message(chid, message.text, parse_mode="Markdown", reply_markup=keyboard)
		Message.create(msg_id = sent.message_id, user_id = sid, msg_type = common, text = message.text)
		#Message.create(user_id = sid, type=common, text = message.text)
	if msg_type == nolike:
		msg_text = re.sub(r'\/nolike', '', message.text)
		sent = bot.send_message(chid, msg_text, parse_mode="Markdown")
		Message.create(msg_id = sent.message_id, user_id = sid, msg_type = nolike, text = msg_text)



@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
	#print(call)
	#is_poll = Poll.select().where(Poll.msg_id == call.message.message_id).count()
	msg = Message.get(Message.msg_id == call.message.message_id)
	e = call.data
	if msg.msg_type == common:
		mark = Like.create_or_get(msg_id = call.message.message_id, user_id = call.from_user.id)

		if mark.like == 0:
			mark.like = emoji[e]
		elif mark.like == 1:
			if e == dislike:
				mark.like = emoji[e]
			elif e == like:
				mark.like = 0
		elif mark.like == -1:
			if e == like:
				mark.like = emoji[e]
			elif e == dislike:
				mark.like = 0
		mark.save()
		
		ls = Like.select().where((Like.like == 1) & (Like.msg_id == mark.msg_id)).count()
		ds = Like.select().where((Like.like == -1) & (Like.msg_id == mark.msg_id)).count()
		post = Post.create_or_get(msg_id = mark.msg_id)
		post.likes = ls
		post.dislikes = ds
		post.save()
		if ls == 0:
			ls = ''

		keyboard = types.InlineKeyboardMarkup()
		like_btn = types.InlineKeyboardButton(text = "{} {}".format(like, ls), callback_data = like)
		dislike_btn = types.InlineKeyboardButton(text = "{} {}".format(ds, dislike), callback_data = dislike)
		#keyboard.add(like_btn, dislike_btn)
		keyboard.add(like_btn)
		bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id,  reply_markup=keyboard)
	
	if msg.msg_type == poll:
		scoreboard = Scoreboard.vote(call.message.message_id, e, call.from_user.id)
		count = Scoreboard.select(fn.Count(Scoreboard.id)).where(Scoreboard.msg_id == call.message.message_id).scalar()
		msg = Message.get(Message.msg_id == call.message.message_id)
		msg_text = msg.text

		keyboard = types.InlineKeyboardMarkup()

		maxpoint = Poll.select(fn.Max(Poll.point)).where(Poll.msg_id == call.message.message_id).scalar()
		for item in Poll.select().where(Poll.msg_id == call.message.message_id).order_by(Poll.point.desc()):
			try:
				percent = item.point / (count / 100)
			except ZeroDivisionError:
				percent = 0
			
			if item.point == 0:
				msg_text += "\n{}  \n {} {}%\n".format(item.item, xlikes(maxpoint, item.point), round(percent))
				btn = types.InlineKeyboardButton(text = "{}".format(item.item), callback_data = item.item)
			else:
				msg_text += "\n{} – {} \n {} {}%\n".format(item.item, item.point, xlikes(maxpoint, item.point), round(percent))
				btn = types.InlineKeyboardButton(text = "{} – {}".format(item.item, item.point), callback_data = item.item)
			keyboard.add(btn)
		msg_text += "\n👥 {}".format(decline(count))
		bot.edit_message_text(chat_id = call.message.chat.id, message_id = call.message.message_id, text = msg_text,  reply_markup=keyboard)
		#bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id,  reply_markup=keyboard)


# section for inline mode
@bot.inline_handler(lambda message: True)
def query_text(message):
	kb = types.InlineKeyboardMarkup()
	# Добавляем колбэк-кнопку с содержимым "test"
	
	results = []
	for m in Message.select().where(Message.user_id == message.from_user.id).order_by(Message.msg_id.desc()):
		print("{} {}".format(m.user_id, m.text))

		kb = types.InlineKeyboardMarkup()
		if m.msg_type == common:
			like_btn = types.InlineKeyboardButton(text = like, callback_data = like)
			dislike_btn = types.InlineKeyboardButton(text = dislike, callback_data = dislike)
			kb.add(like_btn, dislike_btn)

		if m.msg_type == poll:
			for b in Poll.select().where(Poll.msg_id == m.msg_id):
				callback_data = {'item': b.item, 'msg_id': m.msg_id}
				btn = types.InlineKeyboardButton(text = b.item, callback_data = json.dumps(callback_data))
				kb.add(btn)

		
		single_msg = types.InlineQueryResultArticle(
			id=str(m.msg_id), title=m.text,
			input_message_content=types.InputTextMessageContent(message_text=m.text),
			reply_markup = kb
		)
		results.append(single_msg)
	bot.answer_inline_query(inline_query_id = message.id, results = results)



if __name__ == '__main__':
	bot.polling(none_stop=True)

