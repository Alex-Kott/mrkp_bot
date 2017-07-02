import telebot
from telebot import types
import cfg
from peewee import *
import re

bot = telebot.TeleBot(cfg.token)

chid = -1001124459892 # test channel id
like = "👍"
dislike = "👎"
poll = "poll"

emoji = {like : 1, dislike : -1}

db = SqliteDatabase('bot.db')

class Post(Model):
	msg_id = IntegerField(unique = True, primary_key= True)
	likes = IntegerField(default = 0)
	dislikes = IntegerField(default = 0)

	def create_or_get(msg_id):
		try:
			with db.atomic():
				return Post.create(msg_id = msg_id)
		except:
			return Post.select().where(Post.msg_id == msg_id).get()

	class Meta:
		database = db

class Like(Model):
	msg_id = IntegerField()
	like = IntegerField(default = 0) # 1 for like, -1 for dislike, 0 for mark absence
	user_id = IntegerField()

	def create_or_get(msg_id, user_id):
		try:
			with db.atomic():
				return Like.create(msg_id = msg_id, user_id = user_id)
		except:
			# `username` is a unique column, so this username already exists,
			# making it safe to call .get().
			return Like.select().where((Like.msg_id == msg_id) & (Like.user_id == user_id)).get()

	class Meta:
		database = db
		primary_key = CompositeKey('msg_id', 'user_id')

class Poll(Model):
	msg_id = IntegerField()
	item = TextField()
	point = IntegerField()

	def create_or_get(msg_id, item):
		try:
			with db.atomic():
				return Poll.create(msg_id = msg_id, item = item)
		except:
			# `username` is a unique column, so this username already exists,
			# making it safe to call .get().
			return Poll.select().where((Poll.msg_id == msg_id) & (Poll.item = itemm)).get()

	class Meta:
		database = db
		primary_key = CompositeKey('msg_id', 'item')


@bot.message_handler(commands = ['init'])
def init(message):
	Like.create_table(fail_silently = True)
	Post.create_table(fail_silently = True)
	Poll.create_table(fail_silently = True)


@bot.message_handler(content_types=['text'])
def new_post(message):
	print(message)
	sid = message.chat.id
	keyboard = types.InlineKeyboardMarkup()
	poll = re.findall(r'\/poll', message.text)
	if len(poll) > 0:
		try:
			items = re.split(r'\/poll', message.text)[1].strip()
		except:
			bot(sid, "Вы ввели некорректные варианты опроса")
		item = re.split(r'\n', items)
		for i in item:
			poll = Poll.create_or_get()
			btn = types.InlineKeyboardButton(text = i, callback_data = i)
			keyboard.add(btn)

		text = re.sub(r'(\/poll)(\n|.)*', '', message.text)
		bot.send_message(chid, text, parse_mode = "Markdown", reply_markup = keyboard)

		
	else:
		like_btn = types.InlineKeyboardButton(text = like, callback_data = like)
		dislike_btn = types.InlineKeyboardButton(text = dislike, callback_data = dislike)
		keyboard.add(dislike_btn, like_btn)
		bot.send_message(chid, message.text, parse_mode="Markdown", reply_markup=keyboard)



@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
	is_poll = Poll.select().where(Poll.msg_id == call.message.message_id).count()

	if is_poll == 0:
		e = call.data
		
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

		keyboard = types.InlineKeyboardMarkup()
		like_btn = types.InlineKeyboardButton(text = "{} {}".format(ls, like), callback_data = like)
		dislike_btn = types.InlineKeyboardButton(text = "{} {}".format(ds, dislike), callback_data = dislike)
		keyboard.add(dislike_btn, like_btn)
		bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id,  reply_markup=keyboard)
	else:




if __name__ == '__main__':
	Like.create_table(fail_silently = True)
	Post.create_table(fail_silently = True)
	bot.polling(none_stop=True)
