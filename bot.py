import telebot
from telebot import types
from cfg import *
from peewee import *
import re
import ssl
from aiohttp import web


bot = telebot.TeleBot(API_TOKEN)

chid = -1001124459892 # test channel id
like = "👍"
dislike = "👎"
poll = "poll" # пост-опрос
common = "common" # тип поста. обыкновенный пост с лайком и дизлайком под сообщением.

emoji = {like : 1, dislike : -1}

db = SqliteDatabase('bot.db')

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
		lst = (Scoreboard.select(Scoreboard, fn.Count(Scoreboard.user_id).alias('count'))
					    .where(Scoreboard.msg_id == msg_id)
					    .group_by(Scoreboard.item))

		polls = Poll.select().where(Poll.msg_id == msg_id)
		for p in polls:
			count = (Scoreboard.select(fn.Count(Scoreboard.user_id))
							   .where(Scoreboard.msg_id == msg_id & Scoreboard.item == p.item))
			p.point = count
			p.save()

		for i in lst:
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
		try:
			score = Scoreboard.get(Scoreboard.msg_id == msg_id, Scoreboard.user_id == user_id)
			if score.item == item:
				score.delete_instance()
			else:
				score.item = item
			score.save()
		except Exception as e:
			Scoreboard.create(msg_id = msg_id, item = item, user_id = user_id)
		Poll.upd(msg_id)


class Message(BaseModel): # тип сообщения (опрос, обычный пост или что-то ещё). нужен при обработке колбэков
	msg_id = IntegerField(primary_key = True)
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
	sid = message.chat.id
	keyboard = types.InlineKeyboardMarkup()
	poll = re.findall(r'\/poll', message.text)
	if len(poll) > 0:
		try:
			(text, items) = re.split(r'\/poll', message.text)
		except:
			bot(sid, "Вы ввели некорректные варианты опроса")
		item = re.split(r'\n', items.strip())
		for i in item:
			btn = types.InlineKeyboardButton(text = i, callback_data = i)
			keyboard.add(btn)

		sent = bot.send_message(chid, text, parse_mode = "Markdown", reply_markup = keyboard)
		Message.create(msg_id = sent.message_id, type="poll", text = text)
		item = list(set(item))
		for j in item:
			Poll.create(msg_id = sent.message_id, item = j, point = 0)


	else:
		like_btn = types.InlineKeyboardButton(text = like, callback_data = like)
		dislike_btn = types.InlineKeyboardButton(text = dislike, callback_data = dislike)
		keyboard.add(like_btn, dislike_btn)
		sent = bot.send_message(chid, message.text, parse_mode="Markdown", reply_markup=keyboard)
		Message.create(msg_id = sent.message_id, type=common, text = message.text)



@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
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

		keyboard = types.InlineKeyboardMarkup()
		like_btn = types.InlineKeyboardButton(text = "{} {}".format(ls, like), callback_data = like)
		dislike_btn = types.InlineKeyboardButton(text = "{} {}".format(ds, dislike), callback_data = dislike)
		keyboard.add(like_btn, dislike_btn)
		bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id,  reply_markup=keyboard)
	
	if msg.msg_type == poll:
		scoreboard = Scoreboard.vote(call.message.message_id, e, call.from_user.id)
		count = Scoreboard.select(fn.Count(Scoreboard.id)).where(Scoreboard.msg_id == call.message.message_id).scalar()
		
		text = "{}\n👥 Всего проголосовавших: {}".format(msg.text, count)

		keyboard = types.InlineKeyboardMarkup()
		for item in Poll.select().where(Poll.msg_id == call.message.message_id).order_by(Poll.point.desc()):
			try:
				procent = item.point / (count / 100)
			except ZeroDivisionError:
				procent = 0
			btn = types.InlineKeyboardButton(text = "{} — {} ({}%)".format(item.item, item.point, procent), callback_data = item.item)
			keyboard.add(btn)

		#bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id,  reply_markup=keyboard)
		bot.edit_message_text(chat_id = call.message.chat.id, message_id = call.message.message_id, text = text,  reply_markup=keyboard)



app = web.Application()


# Process webhook calls
async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)

app.router.add_post('/{token}/', handle)


if __name__ == '__main__':
	# Remove webhook, it fails sometimes the set if there is a previous webhook
	bot.remove_webhook()


	if LAUNCH_MODE == "DEV":
		bot.polling(none_stop=True)
	elif LAUNCH_MODE == "PROD":
		app = web.Application()
		app.router.add_post('/{token}/', handle)

		
		# Set webhook
		bot.set_webhook(url=WEBHOOK_URL_BASE+WEBHOOK_URL_PATH,
		                certificate=open(WEBHOOK_SSL_CERT, 'r'))

		# Build ssl context
		context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
		context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

		# Start aiohttp server
		web.run_app(
		    app,
		    host=WEBHOOK_LISTEN,
		    port=WEBHOOK_PORT,
		    ssl_context=context,
		)
	